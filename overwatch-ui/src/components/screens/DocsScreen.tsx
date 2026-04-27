import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { useParams, Navigate, Link } from 'react-router-dom';
import { Shield, Download, FileText, LayoutTemplate, Box, Hash } from 'lucide-react';
import { docsRegistry, docsNavigation } from '../../constants/docsRegistry';
import MarkdownRenderer from '../ui/MarkdownRenderer';

function extractToc(content: string) {
  const lines = content.split('\n');
  const toc = [];
  for (const line of lines) {
    const match = line.match(/^(#{2,3})\s+(.*)$/);
    if (match) {
      const level = match[1].length;
      const text = match[2];
      toc.push({ level, text });
    }
  }
  return toc;
}

export default function DocsScreen() {
  const { slug } = useParams<{ slug: string }>();

  // If no slug or invalid slug, redirect to intro
  if (!slug || !docsRegistry[slug]) {
    return <Navigate to="/docs/intro" replace />;
  }

  const currentDoc = docsRegistry[slug];
  const toc = useMemo(() => extractToc(currentDoc.content), [currentDoc.content]);

  const handlePrint = () => {
    window.print();
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="min-h-screen bg-[#F5F2EC] flex flex-col font-['DM_Sans',sans-serif]"
    >
      {/* Top Navbar specifically for Docs */}
      <nav className="h-[60px] bg-[#FFFFFF] border-b border-[rgba(0,0,0,0.07)] flex items-center justify-between px-6 sticky top-0 z-50">
        <Link to="/" className="flex items-center gap-3">
          <div className="w-[28px] h-[28px] rounded-md bg-gradient-to-br from-[#4C63F7] to-[#7C5CF7] flex items-center justify-center shadow-[0_4px_12px_rgba(76,99,247,0.25)]">
            <Shield size={14} color="#fff" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="font-[800] text-[16px] text-[#0F0F0F] tracking-tight">M4 Orchestrator</span>
            <span className="text-[10px] text-[#6B6860] uppercase tracking-wider font-mono">Tanmay - System Lead</span>
          </div>
        </Link>
        <Link to="/" className="text-[#6B6860] hover:text-[#0F0F0F] text-sm font-medium transition-colors">
          &larr; Back to Platform
        </Link>
      </nav>

      {/* Main 3-pane layout */}
      <div className="flex flex-1 max-w-[1400px] w-full mx-auto">
        
        {/* Left Sidebar: Navigation */}
        <aside className="w-[280px] hidden md:flex flex-col border-r border-[rgba(0,0,0,0.07)] bg-[#F5F2EC] py-8 px-6 sticky top-[60px] h-[calc(100vh-60px)] overflow-y-auto">
          {docsNavigation.map((category, idx) => (
            <div key={idx} className="mb-8">
              <h4 className="text-[11px] font-[700] tracking-[0.14em] text-[#4C63F7] uppercase mb-4 font-mono flex items-center gap-2">
                {category.title === 'Platform' && <LayoutTemplate size={12} />}
                {category.title === 'Core Engines' && <Box size={12} />}
                {category.title === 'Technical Specs' && <FileText size={12} />}
                {category.title}
              </h4>
              <ul className="space-y-1">
                {category.items.map((item) => (
                  <li key={item.slug}>
                    <Link
                      to={`/docs/${item.slug}`}
                      className={`block px-3 py-2 rounded-lg text-[14px] font-medium transition-colors ${
                        slug === item.slug
                          ? 'bg-[#EEEBE3] text-[#0F0F0F] shadow-sm border border-[rgba(0,0,0,0.04)]'
                          : 'text-[#6B6860] hover:text-[#0F0F0F] hover:bg-[rgba(0,0,0,0.02)]'
                      }`}
                    >
                      {item.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </aside>

        {/* Center Pane: Markdown Content */}
        <main className="flex-1 min-w-0 py-10 px-8 lg:px-16 bg-[#FFFFFF] min-h-[calc(100vh-60px)] shadow-sm z-10">
          <div className="max-w-[800px] mx-auto">
            {/* Metadata Header */}
            <div className="mb-10 pb-6 border-b border-[rgba(0,0,0,0.07)] flex flex-col md:flex-row md:items-end justify-between gap-4">
              <div>
                <h1 className="text-[36px] md:text-[44px] font-[800] text-[#0F0F0F] leading-tight tracking-tight mb-4">
                  {currentDoc.title}
                </h1>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#0EA872]/10 border border-[#0EA872]/20 text-[#0EA872] text-[11px] font-[700] uppercase tracking-wider font-mono">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#0EA872]"></span>
                    Last Verified: {new Date().toISOString().split('T')[0]}
                  </span>
                  {currentDoc.auditor && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#4C63F7]/10 border border-[#4C63F7]/20 text-[#4C63F7] text-[11px] font-[700] uppercase tracking-wider font-mono">
                      <Shield size={10} />
                      Verified by {currentDoc.auditor}
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={handlePrint}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#FFFFFF] border border-[rgba(0,0,0,0.1)] text-[#0F0F0F] text-[13px] font-[600] shadow-sm hover:bg-[#F5F2EC] transition-all active:scale-[0.98] whitespace-nowrap"
              >
                <Download size={16} />
                Download Brief
              </button>
            </div>

            {/* Markdown Renderer */}
            <div className="pb-20">
              <MarkdownRenderer content={currentDoc.content} />
            </div>
          </div>
        </main>

        {/* Right Sidebar: Table of Contents */}
        <aside className="w-[260px] hidden xl:block bg-[#F5F2EC] border-l border-[rgba(0,0,0,0.07)] py-10 px-6 sticky top-[60px] h-[calc(100vh-60px)] overflow-y-auto">
          <h4 className="text-[11px] font-[700] tracking-[0.14em] text-[#0F0F0F] uppercase mb-5 font-mono flex items-center gap-2">
            On this page
          </h4>
          {toc.length > 0 ? (
            <ul className="space-y-3">
              {toc.map((heading, idx) => (
                <li
                  key={idx}
                  className={`text-[13px] font-medium flex items-start gap-2 ${
                    heading.level === 3 ? 'ml-4 text-[#6B6860]' : 'text-[#0F0F0F]'
                  }`}
                >
                  <Hash size={12} className="mt-0.5 opacity-40 shrink-0" />
                  <span className="leading-tight">{heading.text}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[12px] text-[#6B6860] italic">No headings found.</p>
          )}
        </aside>
      </div>
    </motion.div>
  );
}
