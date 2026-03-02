"""
增强SQL安全模块
提供更严格的SQL注入防护和参数化查询
包含SQL解析查询分析动态查询构建等功能
"""

import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from src.core.exceptions import SQLInjectionException, ValidationException

logger = logging.getLogger(__name__)


class SQLStatementType(Enum):
    """SQL语句类型"""

    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    CREATE = "create"
    ALTER = "alter"
    DROP = "drop"
    UNKNOWN = "unknown"


@dataclass
class SQLSecurityAnalysis:
    """SQL安全分析结果"""

    is_safe: bool
    statement_type: SQLStatementType
    risk_level: str  # "low", "medium", "high", "critical"
    warnings: List[str]
    suggestions: List[str]
    detected_patterns: List[str]


class SQLSecurityAnalyzer:
    """SQL安全分析器"""

    def __init__(self):
        # 危险关键词列表
        self.dangerous_keywords = {
            # DDL语句
            "CREATE",
            "ALTER",
            "DROP",
            "TRUNCATE",
            # DML语句
            "INSERT",
            "UPDATE",
            "DELETE",
            # 权限控制
            "GRANT",
            "REVOKE",
            # 事务控制
            "COMMIT",
            "ROLLBACK",
            "SAVEPOINT",
            # 系统函数
            "LOAD_FILE",
            "INTO_OUTFILE",
            "INTO_DUMPFILE",
            "BENCHMARK",
            "SLEEP",
            "GET_LOCK",
            "RELEASE_LOCK",
            # 系统表
            "information_schema",
            "mysql",
            "sys",
            # 存储过程
            "xp_",
            "sp_",
            # 其他危险操作
            "UNION",
            "JOIN",
        }

        # 允许的SQL关键字只读查询
        self.allowed_keywords = {
            "SELECT",
            "FROM",
            "WHERE",
            "GROUP BY",
            "HAVING",
            "ORDER BY",
            "LIMIT",
            "OFFSET",
            "DISTINCT",
            "AND",
            "OR",
            "NOT",
            "IN",
            "BETWEEN",
            "LIKE",
            "IS NULL",
            "IS NOT NULL",
            "EXISTS",
            "COUNT",
            "SUM",
            "AVG",
            "MIN",
            "MAX",
        }

        # 允许的表名模式
        self.allowed_table_patterns = [r"^videos$", r"^channels$", r"^subtitle_chunks$", r"^retrieval_logs$"]

        # 注入攻击模式
        self.injection_patterns = [
            # SQL注释
            (r"--", "SQL注释"),
            (r"/\*", "多行注释开始"),
            (r"\*/", "多行注释结束"),
            # 布尔盲注
            (r"\bor\b.*\b1\b.*=\b1\b", "OR 1=1模式"),
            (r"\bor\b.*\btrue\b", "OR true模式"),
            # 联合查询
            (r"\bUNION\b.*\bSELECT\b", "UNION注入"),
            (r"\bUNION ALL\b.*\bSELECT\b", "UNION ALL注入"),
            # 系统信息泄露
            (r"\bversion\(\)", "版本信息泄露"),
            (r"\buser\(\)", "用户信息泄露"),
            (r"\bdatabase\(\)", "数据库信息泄露"),
            # 文件操作
            (r"\bINTO\s+\w*OUTFILE\b", "文件写入"),
            (r"\bINTO\s+\w*DUMPFILE\b", "文件导出"),
            # 存储过程
            (r"xp_", "扩展存储过程"),
            (r"sp_", "系统存储过程"),
            # 时间盲注
            (r"\bSLEEP\(", "时间延迟函数"),
            (r"\bBENCHMARK\(", "性能测试函数"),
            # 错误注入
            (r"\bCAST\(", "类型转换错误"),
            (r"\bCONVERT\(", "类型转换错误"),
            # 十六进制编码
            (r"0x[0-9a-f]+", "十六进制编码"),
            # 双编码
            (r"%27", "URL编码单引号"),
            (r"%22", "URL编码双引号"),
        ]

        # SQL解析缓存
        self._parse_cache = {}

    def analyze_sql(self, sql_query: str) -> SQLSecurityAnalysis:
        """分析SQL查询安全性"""
        if not sql_query or not isinstance(sql_query, str):
            raise ValidationException("SQL查询不能为空")

        # 清理查询
        cleaned_query = sql_query.strip()

        # 检查缓存
        if cleaned_query in self._parse_cache:
            return self._parse_cache[cleaned_query]

        warnings = []
        suggestions = []
        detected_patterns = []
        risk_level = "low"

        try:
            # 1. 基本格式检查
            if not cleaned_query:
                warnings.append("SQL查询为空")

            # 2. 解析SQL语句
            statement_type = self._identify_statement_type(cleaned_query)

            # 3. 检查危险关键词
            dangerous_found = self._check_dangerous_keywords(cleaned_query)
            if dangerous_found:
                detected_patterns.extend(dangerous_found)
                risk_level = "high"

            # 4. 检查注入攻击模式
            injection_patterns = self._check_injection_patterns(cleaned_query)
            if injection_patterns:
                detected_patterns.extend(injection_patterns)
                risk_level = "critical"

            # 5. 验证表名
            table_warnings = self._validate_table_names(cleaned_query)
            warnings.extend(table_warnings)

            # 6. 检查查询复杂度
            complexity_issues = self._check_query_complexity(cleaned_query)
            warnings.extend(complexity_issues)

            # 7. 检查字符串长度
            if len(cleaned_query) > 5000:
                warnings.append("SQL查询过长")
                risk_level = "medium"

            # 8. 生成建议
            suggestions = self._generate_suggestions(cleaned_query, warnings)

            # 9. 确定安全性
            is_safe = len(detected_patterns) == 0 and len(warnings) < 3 and risk_level in ["low", "medium"]

            # 10. 创建分析结果
            result = SQLSecurityAnalysis(
                is_safe=is_safe,
                statement_type=statement_type,
                risk_level=risk_level,
                warnings=warnings,
                suggestions=suggestions,
                detected_patterns=detected_patterns,
            )

            # 缓存结果
            self._parse_cache[cleaned_query] = result

            return result

        except Exception as e:
            logger.error(f"SQL分析失败: {e}")
            return SQLSecurityAnalysis(
                is_safe=False,
                statement_type=SQLStatementType.UNKNOWN,
                risk_level="critical",
                warnings=[f"分析过程出错: {str(e)}"],
                suggestions=["请检查SQL查询语法"],
                detected_patterns=[],
            )

    def _identify_statement_type(self, sql_query: str) -> SQLStatementType:
        """识别SQL语句类型"""
        query_upper = sql_query.strip().upper()

        if query_upper.startswith("SELECT"):
            return SQLStatementType.SELECT
        elif query_upper.startswith("INSERT"):
            return SQLStatementType.INSERT
        elif query_upper.startswith("UPDATE"):
            return SQLStatementType.UPDATE
        elif query_upper.startswith("DELETE"):
            return SQLStatementType.DELETE
        elif query_upper.startswith("CREATE"):
            return SQLStatementType.CREATE
        elif query_upper.startswith("ALTER"):
            return SQLStatementType.ALTER
        elif query_upper.startswith("DROP"):
            return SQLStatementType.DROP
        else:
            return SQLStatementType.UNKNOWN

    def _check_dangerous_keywords(self, sql_query: str) -> List[str]:
        """检查危险关键词"""
        query_upper = sql_query.upper()
        found = []

        for keyword in self.dangerous_keywords:
            if keyword in query_upper:
                found.append(keyword)

        return found

    def _check_injection_patterns(self, sql_query: str) -> List[str]:
        """检查注入攻击模式"""
        query_upper = sql_query.upper()
        found = []

        for pattern, description in self.injection_patterns:
            if re.search(pattern, query_upper, re.IGNORECASE):
                found.append(description)

        return found

    def _validate_table_names(self, sql_query: str) -> List[str]:
        """验证表名"""
        warnings = []

        # 提取FROM子句中的表名
        from_pattern = r"\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)"
        matches = re.findall(from_pattern, sql_query, re.IGNORECASE)

        for table_name in matches:
            if not any(re.match(pattern, table_name, re.IGNORECASE) for pattern in self.allowed_table_patterns):
                warnings.append(f"不允许访问表: {table_name}")

        return warnings

    def _check_query_complexity(self, sql_query: str) -> List[str]:
        """检查查询复杂度"""
        warnings = []

        # 检查JOIN数量
        join_count = len(re.findall(r"\bJOIN\b", sql_query, re.IGNORECASE))
        if join_count > 3:
            warnings.append(f"查询包含{join_count}个JOIN复杂度较高")

        # 检查子查询数量
        subquery_count = sql_query.upper().count("SELECT")
        if subquery_count > 1:
            warnings.append(f"查询包含{subquery_count}个子查询")

        # 检查函数调用数量
        function_count = len(re.findall(r"\b\w+\s*\(", sql_query))
        if function_count > 10:
            warnings.append(f"查询包含{function_count}个函数调用")

        return warnings

    def _generate_suggestions(self, sql_query: str, warnings: List[str]) -> List[str]:
        """生成安全建议"""
        suggestions = []

        # 基本建议
        if not re.search(r"\bLIMIT\b", sql_query, re.IGNORECASE):
            suggestions.append("建议添加LIMIT限制结果数量")

        if not re.search(r"\bORDER BY\b", sql_query, re.IGNORECASE):
            suggestions.append("考虑添加ORDER BY进行排序")

        # 性能建议
        if len(warnings) > 0:
            suggestions.append("简化查询结构以提高性能和安全性")

        # 安全建议
        if re.search(r"\bLIKE\b", sql_query, re.IGNORECASE):
            suggestions.append("使用LIKE时注意通配符转义")

        return suggestions

    def validate_parameter(self, param_name: str, param_value: Any) -> bool:
        """验证单个参数"""
        # 检查参数名
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", param_name):
            raise ValidationException(f"不安全的参数名: {param_name}")

        # 检查参数值类型
        if isinstance(param_value, str):
            # 检查字符串值
            if len(param_value) > 1000:
                raise ValidationException(f"参数值过长: {param_name}")

            # 检查是否包含SQL关键字
            param_upper = param_value.upper()
            for keyword in self.dangerous_keywords:
                if keyword in param_upper:
                    raise ValidationException(f"参数值包含危险内容: {param_name}")

        return True

    def build_safe_query(self, base_query: str, parameters: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """构建安全的SQL查询"""
        # 分析基础查询
        analysis = self.analyze_sql(base_query)

        if not analysis.is_safe:
            raise SQLInjectionException(f"SQL查询不安全: {', '.join(analysis.detected_patterns)}")

        # 验证所有参数
        for param_name, param_value in parameters.items():
            self.validate_parameter(param_name, param_value)

        # 确保使用参数化查询
        safe_query = base_query
        safe_params = parameters.copy()

        return safe_query, safe_params


class SQLQueryBuilder:
    """安全SQL查询构建器"""

    def __init__(self):
        self.analyzer = SQLSecurityAnalyzer()

    def build_select_query(
        self,
        table: str,
        columns: List[str] = None,
        where_conditions: Dict[str, Any] = None,
        order_by: str = None,
        limit: int = None,
        offset: int = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """构建安全的SELECT查询"""
        # 验证表名
        if not any(re.match(pattern, table, re.IGNORECASE) for pattern in self.analyzer.allowed_table_patterns):
            raise ValidationException(f"不允许访问表: {table}")

        # 构建查询
        query_parts = ["SELECT"]

        # 添加列
        if columns:
            column_list = ", ".join(columns)
            query_parts.append(column_list)
        else:
            query_parts.append("*")

        query_parts.append(f"FROM {table}")

        parameters = {}

        # 添加WHERE条件
        if where_conditions:
            where_clauses = []
            for i, (key, value) in enumerate(where_conditions.items()):
                param_name = f"param_{i}"
                where_clauses.append(f"{key} = :{param_name}")
                parameters[param_name] = value

            if where_clauses:
                query_parts.append("WHERE " + " AND ".join(where_clauses))

        # 添加ORDER BY
        if order_by:
            query_parts.append(f"ORDER BY {order_by}")

        # 添加LIMIT
        if limit:
            query_parts.append(f"LIMIT {limit}")

        # 添加OFFSET
        if offset:
            query_parts.append(f"OFFSET {offset}")

        query = " ".join(query_parts)

        # 安全分析
        analysis = self.analyzer.analyze_sql(query)
        if not analysis.is_safe:
            raise SQLInjectionException(f"构建的查询不安全: {', '.join(analysis.detected_patterns)}")

        return query, parameters


# === 全局实例 ===
sql_analyzer = SQLSecurityAnalyzer()
sql_builder = SQLQueryBuilder()


# === 使用示例 ===
# # 分析SQL查询
# analysis = sql_analyzer.analyze_sql("SELECT * FROM videos WHERE view_count > 1000")
# if not analysis.is_safe:
#     print(f"查询不安全: {analysis.detected_patterns}")

# # 构建安全查询
# query, params = sql_builder.build_select_query(
#     table="videos",
#     columns=["title", "view_count"],
#     where_conditions={"view_count": 1000},
#     limit=10
# )
