import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface MarkdownRendererProps {
  content: string;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="prose prose-sm md:prose-base max-w-none 
                    prose-headings:font-mono prose-headings:font-bold prose-headings:text-[#0F0F0F]
                    prose-a:text-[#4C63F7] prose-a:no-underline hover:prose-a:underline
                    prose-strong:text-[#0F0F0F] prose-strong:font-bold
                    prose-code:text-[#7C5CF7] prose-code:bg-[#7C5CF715] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:font-mono
                    prose-pre:bg-[#111010] prose-pre:border prose-pre:border-[rgba(255,255,255,0.08)] prose-pre:rounded-xl prose-pre:shadow-lg
                    text-[#6B6860] leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');
            return !inline && match ? (
              <SyntaxHighlighter
                {...props}
                children={String(children).replace(/\n$/, '')}
                style={vscDarkPlus as any}
                language={match[1]}
                PreTag="div"
                customStyle={{
                  background: 'transparent',
                  padding: 0,
                  margin: 0,
                  border: 'none',
                }}
              />
            ) : (
              <code {...props} className={className}>
                {children}
              </code>
            );
          }
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
