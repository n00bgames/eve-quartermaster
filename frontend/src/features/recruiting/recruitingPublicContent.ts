export type PublicDescriptionSection = {
  heading?: string;
  paragraphs: string[];
};

const LEADING_LIST_MARKERS = /^\s*(?:(?:[\u2022\u2713\-\u2013\u2014])\s*|(?:\d+[.)])\s*)+/u;
const CORE_EXPECTATION = /(?:\b(?:minimum\s+)?age\b|\badult\b|\b18\+?\b|\benglish\b|\bdiscord\b|\bvoice\b|\binterview\b|\beve\s+sso\b|\besi\b|\bdoctrine\b|\btrain(?:ing)?\b)/i;

export const RECRUITING_PRIVACY_SUMMARY = "Your application is private and visible only to authorized recruiters. Limited EVE SSO verification is requested later and does not include wallets, assets, mail, contracts, or location data.";

export function normalizeConfiguredLine(value: string): string {
  return value.replace(LEADING_LIST_MARKERS, "").trim();
}

export function normalizedConfiguredLines(items: string[]): string[] {
  return items.map(normalizeConfiguredLine).filter(Boolean);
}

export function initiallyVisibleListIndexes(items: string[], title: string, limit = 6): Set<number> {
  const visible = new Set(items.slice(0, limit).map((_, index) => index));
  if (title === "What we expect") {
    items.forEach((item, index) => {
      if (CORE_EXPECTATION.test(normalizeConfiguredLine(item))) visible.add(index);
    });
  }
  return visible;
}

export function parsePublicDescription(value: string): PublicDescriptionSection[] {
  const sections: PublicDescriptionSection[] = [];
  let heading: string | undefined;
  let paragraphLines: string[] = [];
  let paragraphs: string[] = [];

  const flushParagraph = () => {
    const paragraph = paragraphLines.join(" ").trim();
    if (paragraph) paragraphs.push(paragraph);
    paragraphLines = [];
  };
  const flushSection = () => {
    flushParagraph();
    if (heading || paragraphs.length) sections.push({ heading, paragraphs });
    heading = undefined;
    paragraphs = [];
  };

  value.split(/\r?\n/).forEach((rawLine) => {
    const line = rawLine.trim();
    const headingMatch = line.match(/^#{2,3}\s+(.+)$/);
    if (headingMatch) {
      flushSection();
      heading = headingMatch[1].trim();
    } else if (!line) {
      flushParagraph();
    } else {
      paragraphLines.push(line);
    }
  });
  flushSection();
  return sections;
}
