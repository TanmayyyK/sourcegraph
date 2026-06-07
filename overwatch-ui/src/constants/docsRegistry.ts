// Note: We use ?raw so Vite imports the content as a string.
import introContent from '../content/docs/intro.md?raw';
import forensicsContent from '../content/docs/forensics.md?raw';
import orchestratorContent from '../content/docs/orchestrator.md?raw';
import extractorContent from '../content/docs/extractor.md?raw';
import visionContent from '../content/docs/vision.md?raw';
import contextContent from '../content/docs/context.md?raw';
import deployContent from '../content/docs/deploy.md?raw';

export interface DocCategory {
  title: string;
  items: DocItem[];
}

export interface DocItem {
  slug: string;
  title: string;
  content: string;
  auditor?: string;
}

export const docsRegistry: Record<string, DocItem> = {
  intro: {
    slug: 'intro',
    title: 'Introduction',
    content: introContent,
    auditor: 'Tanmay Kumar',
  },
  forensics: {
    slug: 'forensics',
    title: 'Forensic Pipeline',
    content: forensicsContent,
    auditor: 'Tanmay Kumar',
  },
  orchestrator: {
    slug: 'orchestrator',
    title: 'M4 Orchestrator',
    content: orchestratorContent,
    auditor: 'Tanmay Kumar',
  },
  extractor: {
    slug: 'extractor',
    title: 'M2 Extractor',
    content: extractorContent,
    auditor: 'Tanmay Kumar',
  },
  vision: {
    slug: 'vision',
    title: 'Vision & Ghost Nodes',
    content: visionContent,
    auditor: 'Tanmay Kumar',
  },
  context: {
    slug: 'context',
    title: 'Context Node',
    content: contextContent,
    auditor: 'Tanmay Kumar',
  },
  deploy: {
    slug: 'deploy',
    title: 'Deployment Architecture',
    content: deployContent,
    auditor: 'Tanmay Kumar',
  },
};

export const docsNavigation: DocCategory[] = [
  {
    title: 'Platform',
    items: [
      docsRegistry['intro'],
      docsRegistry['forensics'],
    ],
  },
  {
    title: 'Node Architecture',
    items: [
      docsRegistry['orchestrator'],
      docsRegistry['extractor'],
      docsRegistry['vision'],
      docsRegistry['context'],
    ],
  },
  {
    title: 'Deployment',
    items: [
      docsRegistry['deploy'],
    ],
  },
];