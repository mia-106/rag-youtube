import React from "react";
import { Youtube, Globe } from "lucide-react";
import Image from "next/image";

interface Reference {
  id: string;
  title: string;
  url: string;
  summary?: string;
}

interface SourceCardsProps {
  references: Reference[];
}

export function SourceCards({ references }: SourceCardsProps) {
  if (!references || references.length === 0) return null;

  const getYoutubeId = (url: string | undefined | null) => {
    if (!url) return null;
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
  };

  return (
    <div className="w-full mt-6 border-t border-slate-100 pt-4">
      <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-1">
        参考来源
      </h3>
      <div className="flex overflow-x-auto gap-3 pb-4 scrollbar-thin scrollbar-thumb-slate-200 scrollbar-track-transparent -mx-1 px-1">
        {references.map((ref, index) => {
          const isWeb = ref.id?.startsWith("W") ?? false;
          let safeUrl = ref.url || "";

          // Ensure URL is absolute
          if (safeUrl && !safeUrl.startsWith("http")) {
            safeUrl = "";
          }

          const videoId = getYoutubeId(safeUrl);
          const thumbnailUrl = videoId
            ? `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`
            : null;

          const Wrapper = safeUrl ? 'a' : 'div';
          const wrapperProps = safeUrl ? {
            href: safeUrl,
            target: "_blank",
            rel: "noopener noreferrer"
          } : {};

          return (
            <Wrapper
              key={index}
              id={`source-${ref.id}`}
              {...wrapperProps}
              className={`flex-shrink-0 w-60 bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all duration-300 group ${safeUrl ? "cursor-pointer" : "cursor-default"} ${isWeb ? "hover:border-purple-300 ring-purple-400" : "hover:border-blue-300 ring-blue-400"}`}
            >
              <div className="relative h-32 w-full bg-slate-50 overflow-hidden">
                {thumbnailUrl ? (
                  <div className="relative w-full h-full">
                    <Image
                      src={thumbnailUrl}
                      alt={ref.title}
                      fill
                      className="object-cover group-hover:scale-105 transition-transform duration-500"
                      unoptimized
                    />
                  </div>
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-300">
                    {isWeb ? <Globe className="w-10 h-10" /> : <Youtube className="w-10 h-10" />}
                  </div>
                )}
                <div className="absolute top-2 right-2 bg-black/50 text-white text-[10px] px-1.5 py-0.5 rounded backdrop-blur-sm">
                  文档 {ref.id}
                </div>
              </div>

              <div className="p-3">
                <h4 className={`text-sm font-medium text-slate-800 line-clamp-2 leading-snug mb-2 transition-colors ${isWeb ? "group-hover:text-purple-600" : "group-hover:text-blue-600"}`}>
                  {ref.title}
                </h4>
                {ref.summary && (
                  <p className="text-xs text-slate-500 line-clamp-2">
                    {ref.summary}
                  </p>
                )}
                <div className="mt-2 flex items-center gap-1 text-[10px] text-slate-400 font-medium">
                  {isWeb ? <Globe className="w-3 h-3" /> : <Youtube className="w-3 h-3" />}
                  <span>{isWeb ? "来自：网页搜索" : "来自：YouTube视频"}</span>
                </div>
              </div>
            </Wrapper>
          );
        })}
      </div>
    </div>
  );
}
