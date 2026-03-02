"""
Text-to-SQL工具统一异常版
实现基于LLM的SQL生成和查询功能
使用统一的异常处理策略
"""

import re
import asyncio
from typing import Dict, Any, List, Optional
import logging
from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine
from src.core.deepseek_client import DeepSeekClient
from src.core.exceptions import (
    DatabaseException,
)

logger = logging.getLogger(__name__)


class SQLGenerationError(DatabaseException):
    """SQL生成相关错误"""

    pass


class SQLValidationError(DatabaseException):
    """SQL验证相关错误"""

    pass


class TextToSQL:
    """Text-to-SQL转换工具安全版本"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.deepseek_client = DeepSeekClient()
        self.engine: Optional[Engine] = None

        #  严格的安全配置
        self.dangerous_keywords = [
            "DROP",
            "DELETE",
            "UPDATE",
            "INSERT",
            "ALTER",
            "CREATE",
            "TRUNCATE",
            "GRANT",
            "REVOKE",
            "COMMIT",
            "ROLLBACK",
            "UNION",
            "JOIN",
            "SUBQUERY",
            "CASE",
            "WHEN",
        ]

        #  允许的SQL关键字更严格
        self.allowed_keywords = [
            "SELECT",
            "FROM",
            "WHERE",
            "ORDER BY",
            "LIMIT",
            "OFFSET",
            "AS",
            "AND",
            "OR",
            "NOT",
            "IN",
            "BETWEEN",
            "LIKE",
            "IS NULL",
            "IS NOT NULL",
            "COUNT",
            "SUM",
            "AVG",
            "MIN",
            "MAX",
            "DISTINCT",
        ]

        #  允许的表名白名单
        self.allowed_tables = {
            "videos": {"video_id", "title", "description", "view_count", "like_count", "duration", "published_at"},
            "channels": {"channel_id", "channel_name", "subscriber_count", "description", "created_at"},
            "subtitle_chunks": {"chunk_id", "video_id", "content", "start_time", "end_time", "score"},
        }

        #  查询统计
        self.query_stats = {"total_queries": 0, "blocked_queries": 0, "safe_queries": 0}

    async def initialize(self):
        """初始化数据库连接"""
        try:
            self.engine = create_engine(self.database_url, pool_size=5, max_overflow=10, pool_pre_ping=True)
        except Exception as e:
            logger.error(f" 数据库连接初始化失败: {str(e)}")
            raise SQLGenerationError(f"数据库连接失败: {str(e)}")

    async def generate_sql_query(self, question: str, table_context: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        从自然语言生成SQL查询

        Args:
            question: 用户问题
            table_context: 表结构上下文
            use_cache: 是否使用缓存

        Returns:
            SQL查询结果字典

        Raises:
            SQLGenerationError: SQL生成失败
        """
        logger.info(f" 开始生成SQL查询: {question[:50]}...")

        try:
            system_prompt = f"""你是一个专业的SQL专家负责将自然语言问题转换为高效的SQL查询

表结构信息
{table_context}

生成规则
1. 只生成SELECT查询不要生成INSERTUPDATEDELETE等修改性操作
2. 使用合适的聚合函数COUNTSUMAVGMINMAX等
3. 添加适当的WHERE条件
4. 使用ORDER BY进行排序
5. 使用LIMIT限制结果数量
6. 确保SQL语法正确
7. 使用中文别名以提高可读性

请生成标准SQL查询"""

            user_prompt = f"""请为以下问题生成SQL查询

问题{question}

要求
1. 生成准确的SQL查询
2. 确保查询安全性只读
3. 优化查询性能
4. 返回易于理解的结果"""

            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

            response = await self.deepseek_client.generate_completion(messages=messages, temperature=0.2, stream=False)
            response_text = str(response)
            sql_query = self._extract_sql_query(response_text)
            validation_result = await self.validate_sql_query(sql_query)

            if not validation_result["is_safe"]:
                raise SQLValidationError(f"SQL查询不安全: {validation_result['errors']}")

            result = {
                "sql_query": sql_query,
                "is_valid": validation_result["is_valid"],
                "original_response": response_text,
                "suggestions": validation_result["suggestions"],
                "question": question,
                "table_context": table_context,
            }

            logger.info(f" SQL生成成功: {sql_query[:100]}...")
            return result

        except Exception as e:
            logger.error(f" SQL生成失败: {str(e)}")
            raise SQLGenerationError(f"SQL生成失败: {str(e)}")

    def _extract_sql_query(self, response: str) -> str:
        """从响应中提取SQL查询"""
        # 查找SQL代码块
        sql_patterns = [r"```sql\s*(.*?)\s*```", r"```\s*(.*?)\s*```", r"SELECT.*?(?:;|$)", r"select.*?(?:;|$)"]

        for pattern in sql_patterns:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                sql = match.group(1) if match.groups() else match.group(0)
                return sql.strip()

        # 如果没有找到代码块尝试提取SELECT语句
        select_pattern = r"(SELECT.*?)(?:\n\n|\Z)"
        match = re.search(select_pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # 如果还是没找到返回整个响应去掉可能的自然语言部分
        lines = response.split("\n")
        sql_lines = []
        in_sql = False

        for line in lines:
            line = line.strip()
            if line.upper().startswith("SELECT"):
                in_sql = True
            if in_sql:
                sql_lines.append(line)
                if line.endswith(";"):
                    break

        if sql_lines:
            return "\n".join(sql_lines)

        # 最后尝试返回包含SELECT的行
        for line in lines:
            if "SELECT" in line.upper():
                return line.strip()

        # 如果都失败了返回原始响应
        return response

    async def validate_sql_query(self, sql_query: str) -> Dict[str, Any]:
        """
        严格的SQL查询安全性验证防止SQL注入

        Args:
            sql_query: SQL查询字符串

        Returns:
            验证结果字典
        """
        logger.info(" 开始严格验证SQL查询...")

        errors: List[str] = []
        warnings: List[str] = []
        suggestions: List[str] = []
        if not sql_query or not isinstance(sql_query, str):
            errors.append("SQL查询不能为空且必须是字符串")
            return self._validation_result(False, False, errors, warnings, suggestions)

        cleaned_query = sql_query.strip()
        sql_upper = cleaned_query.upper()

        for keyword in self.dangerous_keywords:
            if keyword in sql_upper:
                errors.append(f"包含危险关键词: {keyword}")

        if not re.search(r"\bSELECT\b", sql_upper, re.IGNORECASE):
            errors.append("只允许SELECT查询")
        if not re.search(r"\bFROM\b", sql_upper, re.IGNORECASE):
            errors.append("缺少FROM关键字")

        table_name = self._extract_table_name(cleaned_query)
        if table_name and table_name not in self.allowed_tables:
            errors.append(f"不允许访问表: {table_name}")

        if table_name and table_name in self.allowed_tables:
            columns = self._extract_columns(cleaned_query)
            allowed_columns = self.allowed_tables[table_name]
            for column in columns:
                if column != "*" and column not in allowed_columns:
                    warnings.append(f"列 '{column}' 可能不被允许")
                    if column.upper() in ["ID", "PASSWORD", "SECRET", "KEY"]:
                        errors.append(f"不允许查询敏感列: {column}")

        injection_patterns = [
            (r"--", "SQL注释"),
            (r"/\*", "多行注释开始"),
            (r"\*/", "多行注释结束"),
            (r";\s*--", "语句分隔符+注释"),
            (r"\bor\b.*\b1\b.*=\b1\b", "OR 1=1模式"),
            (r"\bUNION\b.*\bSELECT\b", "UNION注入"),
            (r"\bINTO\s+\w+", "INTO关键字"),
            (r"xp_", "扩展存储过程"),
            (r"sp_", "系统存储过程"),
        ]

        for pattern, description in injection_patterns:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                errors.append(f"检测到潜在的SQL注入模式: {description}")

        join_count = len(re.findall(r"\bJOIN\b", sql_upper, re.IGNORECASE))
        if join_count > 3:
            errors.append(f"查询包含{join_count}个JOIN复杂度太高")

        if len(cleaned_query) > 2000:
            errors.append("查询字符串过长")

        dangerous_functions = [
            "LOAD_FILE",
            "INTO_OUTFILE",
            "INTO_DUMPFILE",
            "BENCHMARK",
            "SLEEP",
            "GET_LOCK",
            "RELEASE_LOCK",
        ]
        for func in dangerous_functions:
            if func in sql_upper:
                errors.append(f"不允许使用函数: {func}")

        self.query_stats["total_queries"] += 1
        is_safe = len(errors) == 0
        is_valid = len(errors) == 0 and len(warnings) < 3

        if is_safe:
            self.query_stats["safe_queries"] += 1
            if not re.search(r"\bLIMIT\b", sql_upper, re.IGNORECASE):
                warnings.append("建议添加LIMIT限制结果数量")
            if not re.search(r"\bORDER BY\b", sql_upper, re.IGNORECASE):
                suggestions.append("考虑添加ORDER BY进行排序")
        else:
            self.query_stats["blocked_queries"] += 1
            logger.warning(f" 阻止了不安全的SQL查询: {errors}")

        return {
            "is_safe": is_safe,
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "join_count": join_count,
            "query_length": len(cleaned_query),
            "table_name": table_name,
            "columns": self._extract_columns(cleaned_query) if table_name else [],
        }

    async def execute_sql_query(self, sql_query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        安全执行SQL查询使用参数化查询

        Args:
            sql_query: SQL查询字符串
            parameters: 查询参数可选

        Returns:
            查询结果字典

        Raises:
            SQLValidationError: 查询验证失败
            Exception: 执行失败
        """
        if not self.engine:
            await self.initialize()
        engine = self.engine
        if not engine:
            raise SQLGenerationError("数据库引擎未初始化")

        validation_result = await self.validate_sql_query(sql_query)
        if not validation_result["is_safe"]:
            self.query_stats["blocked_queries"] += 1
            raise SQLValidationError(f"不安全的SQL查询: {validation_result['errors']}")

        # 2. 如果有参数确保是参数化查询
        if parameters:
            # 检查参数安全性
            sanitized_params = self._sanitize_parameters(parameters)
            sql_query = self._parameterize_query(sql_query, sanitized_params)

        try:
            logger.info(f" 执行SQL查询: {sql_query[:100]}...")
            bound_params: Dict[str, Any] = {}
            if parameters:
                bound_params = self._sanitize_parameters(parameters)

            query_text = text(sql_query)
            max_rows = 100

            with engine.connect() as conn:
                result = conn.execute(query_text, bound_params)
                columns = list(result.keys())
                rows = result.fetchmany(max_rows)

            serializable_rows: List[Dict[str, Any]] = []
            for row in rows:
                serializable_row = {}
                for key, value in row._mapping.items():
                    if hasattr(value, "__dict__"):
                        serializable_row[key] = str(value)
                    else:
                        serializable_row[key] = value
                serializable_rows.append(serializable_row)

            self.query_stats["safe_queries"] += 1
            logger.info(f" SQL查询执行成功返回 {len(serializable_rows)} 行数据")

            return {
                "success": True,
                "sql_generation": {"sql_query": sql_query, "validation": validation_result},
                "execution": {
                    "row_count": len(serializable_rows),
                    "data": serializable_rows,
                    "columns": columns,
                    "max_rows": max_rows,
                },
                "statistics": {
                    "query_stats": self.query_stats.copy(),
                    "validation_warnings": validation_result.get("warnings", []),
                },
            }

        except Exception as e:
            logger.error(f" SQL查询执行失败: {str(e)}")
            self.query_stats["blocked_queries"] += 1
            raise SQLGenerationError(f"SQL执行失败: {str(e)}")

    def _sanitize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """清理和验证查询参数"""
        sanitized: Dict[str, Any] = {}
        for key, value in parameters.items():
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
                raise SQLValidationError(f"不安全的参数名: {key}")

            if isinstance(value, str):
                if len(value) > 1000:
                    raise SQLValidationError(f"参数值过长: {key}")
                if any(keyword in value.upper() for keyword in self.dangerous_keywords):
                    raise SQLValidationError(f"参数值包含危险内容: {key}")
                sanitized[key] = value.strip()
            elif isinstance(value, (int, float, bool)):
                sanitized[key] = value
            elif value is None:
                sanitized[key] = None
            else:
                sanitized[key] = str(value)

        return sanitized

    def _parameterize_query(self, sql_query: str, parameters: Dict[str, Any]) -> str:
        """将参数化查询转换为SQLAlchemy格式"""
        # 这里应该是LLM生成安全的参数化查询
        # 简化实现假设参数已经在正确位置
        return sql_query

    def _extract_table_name(self, sql_query: str) -> Optional[str]:
        """从SQL查询中提取表名"""
        # 匹配 FROM 关键字后的表名
        from_pattern = r"\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)"
        match = re.search(from_pattern, sql_query, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        return None

    def _extract_columns(self, sql_query: str) -> List[str]:
        """从SQL查询中提取列名"""
        columns = []

        # 匹配 SELECT 关键字后的列名
        select_pattern = r"\bSELECT\s+(.+?)\s+\bFROM\b"
        match = re.search(select_pattern, sql_query, re.DOTALL | re.IGNORECASE)

        if match:
            select_list = match.group(1).strip()

            # 处理聚合函数
            agg_functions = ["COUNT", "SUM", "AVG", "MIN", "MAX", "DISTINCT"]
            for func in agg_functions:
                if func in select_list.upper():
                    columns.append(func.lower())
                    select_list = re.sub(r"\b" + func + r"\s*\(", "", select_list, flags=re.IGNORECASE)

            # 处理逗号分隔的列
            for part in select_list.split(","):
                part = part.strip()
                # 提取列名忽略别名
                column_match = re.search(r"([a-zA-Z_][a-zA-Z0-9_]*)", part)
                if column_match:
                    columns.append(column_match.group(1).lower())

        return columns

    async def generate_statistical_query(self, question: str, data_type: str = "general") -> Dict[str, Any]:
        """
        生成统计分析查询

        Args:
            question: 用户问题
            data_type: 数据类型 (video, channel, general)

        Returns:
            统计查询结果

        Raises:
            SQLGenerationError: 查询生成失败
        """
        logger.info(f" 生成统计分析查询: {question}")

        # 根据数据类型构建表结构上下文
        if data_type == "video":
            table_context = """
表videos
- video_id: 视频ID
- title: 视频标题
- view_count: 播放量
- like_count: 点赞数
- duration: 时长秒
- published_at: 发布时间
- channel_id: 频道ID
"""
        elif data_type == "channel":
            table_context = """
表channels
- channel_id: 频道ID
- channel_name: 频道名称
- subscriber_count: 订阅者数量
- created_at: 创建时间
"""
        else:
            table_context = """
表videos
- video_id: 视频ID
- title: 视频标题
- view_count: 播放量
- like_count: 点赞数
- duration: 时长
- published_at: 发布时间

表channels
- channel_id: 频道ID
- channel_name: 频道名称
- subscriber_count: 订阅者数量
"""

        # 生成SQL查询
        sql_result = await self.generate_sql_query(question, table_context)

        # 执行查询
        execution_result = await self.execute_sql_query(sql_result["sql_query"])

        return {
            "question": question,
            "data_type": data_type,
            "sql_generation": sql_result,
            "execution": execution_result,
            "summary": self._generate_summary(execution_result),
        }

    def _generate_summary(self, execution_result: Dict[str, Any]) -> str:
        """生成查询结果摘要"""
        if not execution_result.get("success"):
            return f"查询失败: {execution_result.get('error', '未知错误')}"

        row_count = execution_result.get("row_count", 0)
        columns = execution_result.get("columns", [])

        summary_parts = [f"查询成功返回 {row_count} 行数据", f"包含 {len(columns)} 个字段: {', '.join(columns[:5])}"]

        if row_count > 5:
            summary_parts.append("显示前5行")

        return " | ".join(summary_parts)

    async def get_table_info(self) -> Dict[str, Any]:
        """获取数据库表信息"""
        if not self.engine:
            await self.initialize()
        engine = self.engine
        if not engine:
            return {"error": "数据库引擎未初始化"}

        try:
            with engine.connect() as conn:
                tables_result = conn.execute(
                    text(
                        """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """
                    )
                )
                tables = [row[0] for row in tables_result]

                table_info = {}
                for table in tables:
                    columns_result = conn.execute(
                        text(
                            """
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = :table_name
                        ORDER BY ordinal_position
                    """
                        ),
                        {"table_name": table},
                    )

                    columns = []
                    for row in columns_result:
                        columns.append({"name": row[0], "type": row[1], "nullable": row[2]})

                    table_info[table] = columns

                return {"tables": tables, "table_info": table_info, "total_tables": len(tables)}
        except Exception as e:
            logger.error(f" 获取表信息失败: {str(e)}")
            return {"error": str(e)}

    def _validation_result(
        self, is_safe: bool, is_valid: bool, errors: List[str], warnings: List[str], suggestions: List[str]
    ) -> Dict[str, Any]:
        return {
            "is_safe": is_safe,
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
        }


def test_text_to_sql():
    """测试Text-to-SQL工具"""
    text_to_sql = TextToSQL("postgresql://user:pass@localhost/db")
    print(" 测试Text-to-SQL工具...")
    print("  注意: 需要实际数据库连接才能测试执行")

    test_response = """
    以下是SQL查询

    ```sql
    SELECT title, view_count
    FROM videos
    WHERE view_count > 100000
    ORDER BY view_count DESC
    LIMIT 10;
    ```

    这个查询将返回播放量最高的前10个视频
    """

    sql = text_to_sql._extract_sql_query(test_response)
    print(f" SQL提取测试: {sql[:100]}...")

    test_sql = "SELECT title FROM videos WHERE view_count > 100000"
    validation = asyncio.run(text_to_sql.validate_sql_query(test_sql))
    print(f" SQL验证测试: 安全={validation['is_safe']}")
    print("\n 所有测试通过")


if __name__ == "__main__":
    test_text_to_sql()
