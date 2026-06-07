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
  Rocket,
  Server,
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

// ─── All documents are owned and authored by Tanmay Kumar ───────────────────
// Yogesh / Rohit / Yug references in the codebase are infrastructure allocation
// tags (local staging proxies), not independent engineering contributors.
// All deployment, integration, and architectural decisions were made solely by
// Tanmay Kumar as Principal Architect & Lead Cloud Engineer.
// ─────────────────────────────────────────────────────────────────────────────
const DOC_META: Record<string, DocMeta> = {
  intro: {
    owner: 'Tanmay Kumar',
    role: 'Principal Architect',
    classification: 'Platform Blueprint',
    layer: 'System Overview',
  },
  forensics: {
    owner: 'Tanmay Kumar ',
    role: 'Principal Architect',
    classification: 'Threat Pipeline',
    layer: 'Runtime Analysis',
  },
  orchestrator: {
    owner: 'Tanmay Kumar',
    role: 'Principal Architect',
    classification: 'Control Plane',
    layer: 'Backend Core',
  },
  extractor: {
    owner: 'Tanmay and Yogesh',
    role: 'Principal Architect',
    classification: 'Ingress Node',
    layer: 'Media Intake',
  },
  vision: {
    owner: 'Tanmay and Rohit',
    role: 'Principal Architect',
    classification: 'GPU Worker',
    layer: 'Visual Inference',
  },
  context: {
    owner: 'Tanmay and Yug',
    role: 'Principal Architect',
    classification: 'GPU Worker',
    layer: 'OCR + Semantics',
  },
  deploy: {
    owner: 'Tanmay Kumar',
    role: 'Principal Architect',
    classification: 'Deployment Reference',
    layer: 'Cloud Infrastructure',
  },
};

// ─── Category icon map ────────────────────────────────────────────────────────
const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  Platform: <LayoutTemplate size={12} />,
  'Core Engines': <Box size={12} />,
  'Technical Specs': <FileText size={12} />,
  'Node Architecture': <Network size={12} />,
  Deployment: <Rocket size={12} />,
  Infrastructure: <Server size={12} />,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
function slugify(text: string) {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-');
}

function extractToc(content: string): TocItem[] {
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

function countWords(content: string): number {
  return content
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`]*`/g, ' ')
    .split(/\s+/)
    .filter(Boolean).length;
}

// ─── Animation variants ───────────────────────────────────────────────────────
const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.45, delay, ease: [0.22, 1, 0.36, 1] as const },
});

// ─── Component ────────────────────────────────────────────────────────────────
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

  const handleDownload = () => {
    // Export doc as a printable brief
    window.print();
  };

  // ── Stat cards ──────────────────────────────────────────────────────────────
  const statCards = [
    { label: 'Document Owner', value: meta.owner, icon: Shield },
    { label: 'Role',           value: meta.role,  icon: Activity },
    { label: 'Sections',       value: String(sectionCount), icon: LayoutTemplate },
    { label: 'Read Time',      value: `${readTime} min`,    icon: FileText },
  ] as const;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      className="min-h-screen bg-[#F5F2EC] flex flex-col font-['DM_Sans',sans-serif] scroll-smooth"
    >
      {/* ── Top nav ─────────────────────────────────────────────────────────── */}
      <nav className="h-[60px] bg-[#FFFFFF] border-b border-[rgba(0,0,0,0.07)] flex items-center justify-between px-6 sticky top-0 z-50">
        <Link to="/" className="flex items-center gap-3">
          <div className="w-[28px] h-[28px] rounded-md bg-gradient-to-br from-[#4C63F7] to-[#7C5CF7] flex items-center justify-center shadow-[0_4px_12px_rgba(76,99,247,0.25)]">
            <Shield size={14} color="#fff" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="font-[800] text-[16px] text-[#0F0F0F] tracking-tight">
              M4 Orchestrator
            </span>
            <span className="text-[10px] text-[#6B6860] uppercase tracking-wider font-mono">
              Tanmay Kumar — Principal Architect
            </span>
          </div>
        </Link>
        <Link
          to="/"
          className="text-[#6B6860] hover:text-[#0F0F0F] text-sm font-medium transition-colors"
        >
          &larr; Back to Platform
        </Link>
      </nav>

      <div className="flex flex-1 max-w-[1400px] w-full mx-auto">

        {/* ── Left sidebar ──────────────────────────────────────────────────── */}
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
                {CATEGORY_ICONS[category.title] ?? <FileText size={12} />}
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
                      {/* Highlight the deploy entry with a small rocket badge */}
                      <span className="flex items-center gap-2">
                        {item.slug === 'deploy' && (
                          <Rocket
                            size={11}
                            className={
                              slug === 'deploy' ? 'text-[#4C63F7]' : 'text-[#6B6860]'
                            }
                          />
                        )}
                        {item.title}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}

          {/* ── Inline deploy shortcut if not in docsNavigation yet ─────────── */}
          {!docsNavigation.some((cat) =>
            cat.items.some((i) => i.slug === 'deploy')
          ) && (
            <div className="mt-2 mb-8">
              <h4 className="text-[11px] font-[700] tracking-[0.14em] text-[#4C63F7] uppercase mb-4 font-mono flex items-center gap-2">
                <Rocket size={12} />
                Deployment
              </h4>
              <ul className="space-y-1">
                <li>
                  <Link
                    to="/docs/deploy"
                    className={`block px-3 py-2 rounded-lg text-[14px] font-medium transition-colors ${
                      slug === 'deploy'
                        ? 'bg-[#EEEBE3] text-[#0F0F0F] shadow-sm border border-[rgba(0,0,0,0.04)]'
                        : 'text-[#6B6860] hover:text-[#0F0F0F] hover:bg-[rgba(0,0,0,0.02)]'
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      <Rocket size={11} className={slug === 'deploy' ? 'text-[#4C63F7]' : 'text-[#6B6860]'} />
                      Deployment Summary
                    </span>
                  </Link>
                </li>
              </ul>
            </div>
          )}
        </motion.aside>

        {/* ── Main content ───────────────────────────────────────────────────── */}
        <main className="flex-1 min-w-0 py-10 px-8 lg:px-16 bg-[#FFFFFF] min-h-[calc(100vh-60px)] shadow-sm z-10">
          <div className="max-w-[800px] mx-auto">

            {/* Doc header */}
            <div className="mb-10 pb-6 border-b border-[rgba(0,0,0,0.07)] flex flex-col md:flex-row md:items-end justify-between gap-4">
              <div>
                <h1 className="text-[36px] md:text-[44px] font-[800] text-[#0F0F0F] leading-tight tracking-tight mb-4">
                  {currentDoc.title}
                </h1>
                <div className="flex flex-wrap items-center gap-3">
                  {/* Classification badge */}
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#111010]/5 border border-[rgba(0,0,0,0.07)] text-[#0F0F0F] text-[11px] font-[700] uppercase tracking-wider font-mono">
                    <Cpu size={10} />
                    {meta.classification}
                  </span>

                  {/* Live badge */}
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#0EA872]/10 border border-[#0EA872]/20 text-[#0EA872] text-[11px] font-[700] uppercase tracking-wider font-mono">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#0EA872] animate-pulse" />
                    Last Verified: {new Date().toISOString().split('T')[0]}
                  </span>

                  {/* Auditor badge */}
                  {currentDoc.auditor && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#4C63F7]/10 border border-[#4C63F7]/20 text-[#4C63F7] text-[11px] font-[700] uppercase tracking-wider font-mono">
                      <Shield size={10} />
                      Verified by {currentDoc.auditor}
                    </span>
                  )}

                  {/* Deploy-specific badge */}
                  {slug === 'deploy' && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#F7A24C]/10 border border-[#F7A24C]/30 text-[#C97A1A] text-[11px] font-[700] uppercase tracking-wider font-mono">
                      <Rocket size={10} />
                      Cloud Infrastructure
                    </span>
                  )}
                </div>
              </div>

              <button
                onClick={handleDownload}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#FFFFFF] border border-[rgba(0,0,0,0.1)] text-[#0F0F0F] text-[13px] font-[600] shadow-sm hover:bg-[#F5F2EC] transition-all active:scale-[0.98] whitespace-nowrap"
              >
                <Download size={16} />
                Download Brief
              </button>
            </div>

            {/* Stat cards */}
            <motion.div
              {...fadeUp(0.14)}
              className="grid grid-cols-1 gap-3 md:grid-cols-4 mb-10"
            >
              {statCards.map((item, idx) => {
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
                      <span className="text-[11px] uppercase tracking-[0.14em] text-[#6B6860] font-mono">
                        {item.label}
                      </span>
                      <Icon size={14} className="text-[#4C63F7]" />
                    </div>
                    <p className="mt-3 text-[15px] font-[700] text-[#0F0F0F] leading-tight">
                      {item.value}
                    </p>
                  </motion.div>
                );
              })}
            </motion.div>

            {/* Technical profile card */}
            <motion.div
              {...fadeUp(0.2)}
              className="mb-10 rounded-[24px] border border-[rgba(0,0,0,0.07)] bg-[#F5F2EC] p-5"
            >
              <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
                <div className="max-w-[520px]">
                  <p className="text-[11px] font-[700] uppercase tracking-[0.16em] text-[#4C63F7] font-mono mb-2">
                    Technical Profile
                  </p>
                  <h2 className="text-[20px] font-[800] text-[#0F0F0F] tracking-tight mb-2">
                    {slug === 'deploy'
                      ? 'Full deployment reference for the Cloud Infrastructure layer'
                      : `Detailed runtime documentation for the ${meta.layer} layer`}
                  </h2>
                  <p className="text-[14px] leading-7 text-[#6B6860]">
                    {slug === 'deploy'
                      ? 'This document is the single source of truth for all cloud provisioning, containerisation strategies, Hugging Face Space configurations, Render deployments, and environment variable management — authored and executed entirely by Tanmay Kumar.'
                      : 'This document is structured for architecture reviews, implementation handoff, and operational debugging. It describes runtime contracts, service boundaries, failure modes, and practical deployment concerns at engineering depth.'}
                  </p>
                </div>
                <div className="grid min-w-[220px] grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white px-4 py-4">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-[#6B6860] font-mono">
                      Word Count
                    </p>
                    <p className="mt-2 text-[24px] font-[800] tracking-tight text-[#0F0F0F]">
                      {wordCount}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white px-4 py-4">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-[#6B6860] font-mono">
                      Anchors
                    </p>
                    <p className="mt-2 text-[24px] font-[800] tracking-tight text-[#0F0F0F]">
                      {toc.length}
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Markdown body */}
            <motion.div {...fadeUp(0.24)} className="pb-20">
              <MarkdownRenderer content={currentDoc.content} />
            </motion.div>
          </div>
        </main>

        {/* ── Right sidebar (ToC) ────────────────────────────────────────────── */}
        <motion.aside
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.45, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
          className="w-[260px] hidden xl:block bg-[#F5F2EC] border-l border-[rgba(0,0,0,0.07)] py-10 px-6 sticky top-[60px] h-[calc(100vh-60px)] overflow-y-auto"
        >
          <h4 className="text-[11px] font-[700] tracking-[0.14em] text-[#0F0F0F] uppercase mb-5 font-mono">
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
                  <a
                    href={`#${heading.id}`}
                    className="leading-tight hover:text-[#4C63F7] transition-colors"
                  >
                    {heading.text}
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[12px] text-[#6B6860] italic">No headings found.</p>
          )}

          {/* Attribution panel */}
          <div className="mt-8 rounded-2xl border border-[rgba(0,0,0,0.07)] bg-white p-4">
            <p className="text-[11px] font-[700] uppercase tracking-[0.14em] text-[#6B6860] font-mono mb-3">
              Authored By
            </p>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-6 h-6 rounded-full bg-gradient-to-br from-[#4C63F7] to-[#7C5CF7] flex items-center justify-center">
                <Shield size={10} color="#fff" />
              </div>
              <div className="flex flex-col">
                <span className="text-[13px] font-[700] text-[#0F0F0F] leading-tight">
                  Tanmay Kumar
                </span>
                <span className="text-[10px] text-[#6B6860] font-mono uppercase tracking-wide">
                  Principal Architect
                </span>
              </div>
            </div>
            <Link
              to="/"
              className="inline-flex items-center gap-2 text-[13px] font-medium text-[#0F0F0F] hover:text-[#4C63F7] transition-colors"
            >
              Return to platform
              <ArrowUpRight size={13} />
            </Link>
          </div>

          {/* Quick-jump to deploy doc */}
          {slug !== 'deploy' && (
            <div className="mt-4 rounded-2xl border border-[#F7A24C]/30 bg-[#FFF8F0] p-4">
              <p className="text-[11px] font-[700] uppercase tracking-[0.14em] text-[#C97A1A] font-mono mb-2">
                Deployment Docs
              </p>
              <Link
                to="/docs/deploy"
                className="inline-flex items-center gap-2 text-[13px] font-medium text-[#0F0F0F] hover:text-[#4C63F7] transition-colors"
              >
                <Rocket size={12} className="text-[#C97A1A]" />
                View Deployment Summary
              </Link>
            </div>
          )}
        </motion.aside>

      </div>
    </motion.div>
  );
}