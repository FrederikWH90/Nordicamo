// Example input: Nordicamo's own About text (no third-party copyright).
export const EXAMPLE_TEXT = `Nordicamo (Nordic Alternative Media Observatory) is a comparative platform for studying alternative news media in Denmark, Finland, Norway and Sweden.

Here, alternative news media means publisher-operated outlets that position themselves as alternatives to mainstream journalism, political institutions or dominant public narratives. The observatory covers outlet websites, not social media accounts.

It offers structured data and descriptive analytics for comparing publication patterns, outlet structures and topics across countries and over time, and supports case selection, documentation and exploratory analysis. Nordicamo is not a complete census of alternative media activity, nor an evaluation of outlets' influence, audience reach or societal impact.

An outlet is included when it shows sustained publication activity and a clear alternative positioning in its self-descriptions, editorial statements or consistent framing. Country experts help identify outlets and validate their relevance. The outlet list is versioned, documenting additions, removals and the reasons for them.

Starting from a seed list of outlet domains, article URLs are collected from sitemaps where available, and otherwise from site structures such as category and archive pages; some outlets require custom scrapers. Collection respects robots.txt and uses rate limits and backoff to minimise server load. Outlets that block automated access, rely heavily on dynamic rendering or give unreliable timestamps may be only partly covered.

Text is extracted with Trafilatura, cleaned of boilerplate and normalised into a common schema: publication date, outlet, domain, country, URL and main text. Quality checks include routine sampling of extraction quality, duplicate detection where feasible, and date verification.

Nordicamo is descriptive and exploratory. It highlights high-level patterns in alternative news production: total output, distribution across countries, outlet concentration, trends over time and, where available, topics. These summaries help users detect shifts and spikes, compare countries and guide qualitative work such as close reading, case selection and interpretive analysis.

Nordicamo is designed for research on politically sensitive material and uses safeguards to reduce potential harm. Only publicly accessible content is collected, with respect for site policies and operational limits. Access to raw content is restricted, with access tiers, logging and retention and deletion practices. Public outputs favour aggregated summaries.`;
