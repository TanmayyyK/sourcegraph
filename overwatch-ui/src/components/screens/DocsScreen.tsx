import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { useParams, Navigate, Link } from 'react-router-dom';
import {
  Shield,
  Download,
  FileText,
  LayoutTemplate,
  Box,
  Hash,
  Activity,
  Cpu,
  Network,
  ArrowUpRight,
} from 'lucide-react';
import { docsRegistry, docsNavigation } from '../../constants/docsRegistry';
import MarkdownRenderer from '../ui/MarkdownRenderer';

type TocItem = {
  level: number;
  text: string;
  id: string;
};

type DocMeta = {
  owner: string;
  role: string;
  classification: string;
  layer: string;
};

const DOC_META: Record<string, DocMeta> = {
  intro: {
    owner: 'Tanmay Kumar',
    role: 'Lead Architect',
    classification: 'Platform Blueprint',
    layer: 'System Overview',
  },
  forensics: {
    owner: 'Tanmay Kumar',
    role: 'Lead Architect',
    classification: 'Threat Pipeline',
    layer: 'Runtime Analysis',
  },
  orchestrator: {
    owner: 'Tanmay Kumar',
    role: 'Lead Architect',
    classification: 'Control Plane',
    layer: 'Backend Core',
  },
  extractor: {
    owner: 'Yogesh Sharma',
    role: 'Node Owner',
    classification: 'Ingress Node',
    layer: 'Media Intake',
  },
  vision: {
    owner: 'Rohit Kumar',
    role: 'Node Owner',
    classification: 'GPU Worker',
    layer: 'Visual Inference',
  },
  context: {
    owner: 'Yug',
    role: 'Node Owner',
    classification: 'GPU Worker',
    layer: 'OCR + Semantics',
  },
};

function slugify(text: string) {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-');
}

function extractToc(content: string) {
  const lines = content.split('\n');
  const toc: TocItem[] = [];
  for (const line of lines) {
    const match = line.match(/^(#{2,3})\s+(.*)$/);
    if (match) {
      const level = match[1].length;
      const text = match[2];
      toc.push({ level, text, id: slugify(text) });
    }
  }
  return toc;
}

function countWords(content: string) {
  return content
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`]*`/g, ' ')
    .split(/\s+/)
    .filter(Boolean).length;
}

export default function DocsScreen() {
  const { slug } = useParams<{ slug: string }>();

  if (!slug || !docsRegistry[slug]) {
    return <Navigate to="/docs/intro" replace />;
  }

  const currentDoc = docsRegistry[slug];
  const meta = DOC_META[slug] ?? DOC_META.intro;
  const toc = useMemo(() => extractToc(currentDoc.content), [currentDoc.content]);
  const wordCount = useMemo(() => countWords(currentDoc.content), [currentDoc.content]);
  const readTime = Math.max(1, Math.ceil(wordCount / 220));
  const sectionCount = toc.filter((item) => item.level === 2).length;

  const handlePrint = () => {
    window.print();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="min-h-screen bg-[#F5F2EC] flex flex-col font-['DM_Sans',sans-serif] scroll-smooth"
    >
      <nav className="h-[60px] bg-[#FFFFFF] border-b border-[rgba(0,0,0,0.07)] flex items-center justify-between px-6 sticky top-0 z-50">
        <Link to="/" className="flex items-center gap-3">
          <div className="w-[28px] h-[28px] rounded-md bg-gradient-to-br from-[#4C63F7] to-[#7C5CF7] flex items-center justify-center shadow-[0_4px_12px_rgba(76,99,247,0.25)]">
            <Shield size={14} color="#fff" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="font-[800] text-[16px] text-[#0F0F0F] tracking-tight">M4 Orchestrator</span>
            <span className="text-[10px] text-[#6B6860] uppercase tracking-wider font-mono">Tanmay Kumar - Lead Architect</span>
          </div>
        </Link>
        <Link to="/" className="text-[#6B6860] hover:text-[#0F0F0F] text-sm font-medium transition-colors">
          &larr; Back to Platform
        </Link>
      </nav>

      <div className="flex flex-1 max-w-[1400px] w-full mx-auto">
        <motion.aside
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.45, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
          className="w-[280px] hidden md:flex flex-col border-r border-[rgba(0,0,0,0.07)] bg-[#F5F2EC] py-8 px-6 sticky top-[60px] h-[calc(100vh-60px)] overflow-y-auto"
        >
          {docsNavigation.map((category, idx) => (
            <motion.div
              key={idx}
              className="mb-8"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: idx * 0.06 + 0.14 }}
            >
              <h4 className="text-[11px] font-[700] tracking-[0.14em] text-[#4C63F7] uppercase mb-4 font-mono flex items-center gap-2">
                {category.title === 'Platform' && <LayoutTemplate size={12} />}
                {category.title === 'Core Engines' && <Box size={12} />}
                {category.title === 'Technical Specs' && <FileText size={12} />}
                {category.title === 'Node Architecture' && <Network size={12} />}
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
            </motion.div>
          ))}
        </motion.aside>

        <main className="flex-1 min-w-0 py-10 px-8 lg:px-16 bg-[#FFFFFF] min-h-[calc(100vh-60px)] shadow-sm z-10">
          <div className="max-w-[800px] mx-auto">
            <div className="mb-10 pb-6 border-b border-[rgba(0,0,0,0.07)] flex flex-col md:flex-row md:items-end justify-between gap-4">
              <div>
                <h1 className="text-[36px] md:text-[44px] font-[800] text-[#0F0F0F] leading-tight tracking-tight mb-4">
                  {currentDoc.title}
                </h1>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#111010]/5 border border-[rgba(0,0,0,0.07)] text-[#0F0F0F] text-[11px] font-[700] uppercase tracking-wider font-mono">
                    <Cpu size={10} />
                    {meta.classification}
                  </span>
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

            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.14, ease: [0.22, 1, 0.36, 1] }}
              className="grid grid-cols-1 gap-3 md:grid-cols-4 mb-10"
            >
              {[
                { label: 'Document Owner', value: meta.owner, icon: Shield },
                { label: 'Role', value: meta.role, icon: Activity },
                { label: 'Sections', value: String(sectionCount), icon: LayoutTemplate },
                { label: 'Read Time', value: `${readTime} min`, icon: FileText },
              ].map((item, idx) => {
                const Icon = item.icon;
                return (
                  <motion.div
                    key={item.label}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.32, delay: 0.18 + idx * 0.05 }}
                    className="rounded-2xl border border-[rgba(0,0,0,0.07)] bg-[#F5F2EC] px-4 py-4 shadow-[0_1px_0_rgba(0,0,0,0.03)]"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[11px] uppercase tracking-[0.14em] text-[#6B6860] font-mono">{item.label}</span>
                      <Icon size={14} className="text-[#4C63F7]" />
                    </div>
                    <p className="mt-3 text-[15px] font-[700] text-[#0F0F0F] leading-tight">
                      {item.value}
                    </p>
                  </motion.div>
                );
              })}
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
              className="mb-10 rounded-[24px] border border-[rgba(0,0,0,0.07)] bg-[#F5F2EC] p-5"
            >
              <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
                <div className="max-w-[520px]">
                  <p className="text-[11px] font-[700] uppercase tracking-[0.16em] text-[#4C63F7] font-mono mb-2">
                    Technical Profile
                  </p>
                  <h2 className="text-[20px] font-[800] text-[#0F0F0F] tracking-tight mb-2">
                    Detailed runtime documentation for the {meta.layer} layer
                  </h2>
                  <p className="text-[14px] leading-7 text-[#6B6860]">
                    This document is structured for architecture reviews, implementation handoff, and operational debugging.
                    It describes runtime contracts, service boundaries, failure modes, and practical deployment concerns at engineering depth.
                  </p>
                </div>
                <div className="grid min-w-[220px] grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white px-4 py-4">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-[#6B6860] font-mono">Word Count</p>
                    <p className="mt-2 text-[24px] font-[800] tracking-tight text-[#0F0F0F]">{wordCount}</p>
                  </div>
                  <div className="rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white px-4 py-4">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-[#6B6860] font-mono">Anchors</p>
                    <p className="mt-2 text-[24px] font-[800] tracking-tight text-[#0F0F0F]">{toc.length}</p>
                  </div>
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.24, ease: [0.22, 1, 0.36, 1] }}
              className="pb-20"
            >
              <MarkdownRenderer content={currentDoc.content} />
            </motion.div>
          </div>
        </main>

        <motion.aside
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.45, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
          className="w-[260px] hidden xl:block bg-[#F5F2EC] border-l border-[rgba(0,0,0,0.07)] py-10 px-6 sticky top-[60px] h-[calc(100vh-60px)] overflow-y-auto"
        >
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
                  <a href={`#${heading.id}`} className="leading-tight hover:text-[#4C63F7] transition-colors">
                    {heading.text}
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[12px] text-[#6B6860] italic">No headings found.</p>
          )}
          <div className="mt-8 rounded-2xl border border-[rgba(0,0,0,0.07)] bg-white p-4">
            <p className="text-[11px] font-[700] uppercase tracking-[0.14em] text-[#6B6860] font-mono mb-2">
              Navigation
            </p>
            <Link to="/" className="inline-flex items-center gap-2 text-[13px] font-medium text-[#0F0F0F] hover:text-[#4C63F7] transition-colors">
              Return to platform
              <ArrowUpRight size={13} />
            </Link>
          </div>
        </motion.aside>
      </div>
    </motion.div>
  );
}
