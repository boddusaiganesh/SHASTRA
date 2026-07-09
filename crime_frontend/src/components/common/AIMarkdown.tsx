import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';

interface AIMarkdownProps {
  text: string;
  className?: string;
}

const AIMarkdown: React.FC<AIMarkdownProps> = ({ text, className = "" }) => {
  return (
    <div className={`ai-markdown-container ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          strong: ({ node, ...props }) => <span className="font-bold text-blue-100" {...props} />,
          h1: ({ node, ...props }) => <h1 className="font-bold text-base text-white mb-2 mt-4" {...props} />,
          h2: ({ node, ...props }) => <h2 className="font-bold text-sm text-white mb-2 mt-3" {...props} />,
          h3: ({ node, ...props }) => <h3 className="font-semibold text-white mb-1 mt-2 text-sm" {...props} />,
          ul: ({ node, ...props }) => <ul className="list-disc pl-4 space-y-1 my-2" {...props} />,
          ol: ({ node, ...props }) => <ol className="list-decimal pl-4 space-y-1 my-2" {...props} />,
          p: ({ node, ...props }) => <p className="mb-2 last:mb-0 leading-relaxed" {...props} />,
          li: ({ node, ...props }) => <li className="text-slate-200" {...props} />,
          a: ({ node, ...props }) => <a className="text-blue-400 hover:underline" target="_blank" rel="noopener noreferrer" {...props} />,
          blockquote: ({ node, ...props }) => <blockquote className="border-l-4 border-blue-500/50 pl-3 py-1 my-2 bg-blue-900/10 italic text-slate-300" {...props} />,
          code: ({ node, inline, ...props }: any) => 
            inline 
              ? <code className="bg-slate-800/80 text-blue-300 px-1 py-0.5 rounded text-xs font-mono" {...props} />
              : <div className="bg-slate-900 rounded-md p-3 my-3 overflow-x-auto border border-slate-700/50"><code className="text-xs font-mono text-slate-300" {...props} /></div>,
          table: ({ node, ...props }) => <div className="overflow-x-auto my-3 border border-slate-700/50 rounded-lg"><table className="w-full text-left border-collapse" {...props} /></div>,
          th: ({ node, ...props }) => <th className="border-b border-slate-700/80 bg-slate-800/80 px-3 py-2 text-xs font-semibold text-slate-200 uppercase tracking-wider" {...props} />,
          td: ({ node, ...props }) => <td className="border-b border-slate-700/50 px-3 py-2 text-sm text-slate-300" {...props} />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
};

export default AIMarkdown;
