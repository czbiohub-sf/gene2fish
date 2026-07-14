const ZFIN_PUBLICATIONS = [
  {
    id: "ZDB-PUB-220216-32",
    year: 2022,
    authors:
      "Bradford YM, Van Slyke CE, Ruzicka L, Singer A, Eagle A, Fashena D, Howe DG, Frazer K, Martin R, Paddock H, Pich C, Ramachandran S, Westerfield M",
    title:
      "Zebrafish information network, the knowledgebase for Danio rerio research",
  },
  {
    id: "ZDB-PUB-010810-1",
    year: 2001,
    authors: "Thisse B, Pflumio S, Fürthauer M, Loppin B, Heyer V, Degrave A, Woehl R, Lux A, Steffan T, Charbonnier XQ, Thisse C",
    title: "Expression of the zebrafish genome during embryogenesis (NIH R01 RR15402)",
  },
  {
    id: "ZDB-PUB-040907-1",
    year: 2004,
    authors: "Thisse B, Thisse C",
    title: "Fast Release Clones: A High Throughput Expression Analysis",
  },
  {
    id: "ZDB-PUB-051025-1",
    year: 2005,
    authors: "Thisse C, Thisse B",
    title: "High Throughput Expression Analysis of ZF-Models Consortium Clones",
  },
  {
    id: "ZDB-PUB-080220-1",
    year: 2008,
    authors: "Thisse C, Thisse B",
    title: "Unexpected Novel Relational Links Uncovered by Extensive Developmental Profiling of Nuclear Receptor Expression",
  },
  {
    id: "ZDB-PUB-080227-22",
    year: 2008,
    authors: "Thisse B, Wright GJ, Thisse C",
    title: "Embryonic and Larval Expression Patterns from a Large Scale Screening for Novel Low Affinity Extracellular Protein Interactions",
  },
];

export function Attribution() {
  return (
    <footer className="app-footer">
      <div className="footer-license">
        Images from{" "}
        <a href="https://zfin.org" target="_blank" rel="noopener noreferrer">
          ZFIN (zfin.org)
        </a>
        . Thisse et al. high-throughput <em>in situ</em> hybridization data.
        Licensed under{" "}
        <a
          href="https://creativecommons.org/licenses/by/4.0/"
          target="_blank"
          rel="noopener noreferrer"
        >
          CC BY 4.0
        </a>
        .
      </div>

      <div className="footer-references">
        <span className="footer-references-label">References</span>
        <ol className="footer-ref-list">
          {ZFIN_PUBLICATIONS.map((pub) => (
            <li key={pub.id}>
              {pub.authors} ({pub.year}). {pub.title}.{" "}
              <a
                href={`https://zfin.org/${pub.id}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                ZFIN: {pub.id}
              </a>
            </li>
          ))}
        </ol>
      </div>

      <div className="footer-creators">
        Created by Vera Janssen, Leandro Lima &amp; Wellington Rutes
      </div>
    </footer>
  );
}
