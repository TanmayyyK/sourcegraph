
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type { ReactNode } from 'react';

interface MarkdownRendererProps {
  content: string;
}

function flattenText(children: ReactNode): string {
  if (typeof children === 'string' || typeof children === 'number') {
    return String(children);
  }
  if (Array.isArray(children)) {
    return children.map(flattenText).join('');
  }
  if (children && typeof children === 'object' && 'props' in children) {
    return flattenText((children as { props?: { children?: ReactNode } }).props?.children ?? '');
  }
  return '';
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-');
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="prose prose-sm md:prose-base max-w-none 
                    prose-headings:font-mono prose-headings:font-bold prose-headings:text-[#0F0F0F]
                    prose-a:text-[#4C63F7] prose-a:no-underline hover:prose-a:underline
                    prose-strong:text-[#0F0F0F] prose-strong:font-bold
                    prose-h1:scroll-mt-24 prose-h2:scroll-mt-24 prose-h3:scroll-mt-24
                    prose-table:w-full prose-table:border-collapse prose-th:border prose-th:border-[rgba(0,0,0,0.08)] prose-th:bg-[#F5F2EC] prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:text-[#0F0F0F]
                    prose-td:border prose-td:border-[rgba(0,0,0,0.08)] prose-td:px-3 prose-td:py-2
                    prose-ul:marker:text-[#4C63F7] prose-ol:marker:text-[#4C63F7]
                    prose-code:text-[#7C5CF7] prose-code:bg-[#7C5CF715] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:font-mono
                    prose-pre:bg-[#111010] prose-pre:border prose-pre:border-[rgba(255,255,255,0.08)] prose-pre:rounded-xl prose-pre:shadow-lg
                    text-[#6B6860] leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1({ children, ...props }) {
            const id = slugify(flattenText(children));
            return <h1 id={id} {...props}>{children}</h1>;
          },
          h2({ children, ...props }) {
            const id = slugify(flattenText(children));
            return <h2 id={id} {...props}>{children}</h2>;
          },
          h3({ children, ...props }) {
            const id = slugify(flattenText(children));
            return <h3 id={id} {...props}>{children}</h3>;
          },
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
