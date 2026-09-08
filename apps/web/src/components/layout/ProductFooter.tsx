import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { projectLinks, type ProjectLinkKey } from "../../config/project";

const PROJECT_LINK_KEYS: ProjectLinkKey[] = [
  "github",
  "documentation",
  "privacy",
  "license",
];

function isExternal(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

export function ProductFooter() {
  const { t } = useTranslation();
  const configuredLinks = useMemo(
    () => new Map(projectLinks().map((link) => [link.key, link])),
    [],
  );

  return (
    <footer className="product-footer">
      <div className="product-footer-inner">
        <div className="footer-grid">
          <section className="footer-identity" aria-labelledby="footer-product">
            <h2 id="footer-product" className="footer-wordmark">
              DeID
            </h2>
            <p className="footer-descriptor">{t("footer.descriptor")}</p>
            <p className="footer-promise">
              {t("footer.detect")}
              <br />
              {t("footer.control")}
            </p>
            <p className="footer-metadata">
              <strong>{t("footer.metadata.openSource")}</strong>
              <span aria-hidden="true"> · </span>
              {t("footer.metadata.local")}
              <span aria-hidden="true"> · </span>
              {t("footer.metadata.api")}
            </p>
          </section>

          <section
            className="footer-principles"
            aria-labelledby="footer-principles"
          >
            <h2 id="footer-principles">{t("footer.principles.title")}</h2>
            <dl>
              <div>
                <dt>{t("footer.principles.local.title")}</dt>
                <dd>{t("footer.principles.local.body")}</dd>
              </div>
              <div>
                <dt>{t("footer.principles.model.title")}</dt>
                <dd>{t("footer.principles.model.body")}</dd>
              </div>
              <div>
                <dt>{t("footer.principles.control.title")}</dt>
                <dd>{t("footer.principles.control.body")}</dd>
              </div>
            </dl>
          </section>

          <nav className="footer-project" aria-labelledby="footer-project">
            <h2 id="footer-project">{t("footer.project.title")}</h2>
            <ul>
              {PROJECT_LINK_KEYS.map((key) => {
                const link = configuredLinks.get(key);
                if (!link) {
                  return (
                    <li key={key}>
                      <span className="footer-link-unavailable">
                        {t(`footer.project.links.${key}`)}
                      </span>
                    </li>
                  );
                }
                const external = isExternal(link.url);
                return (
                  <li key={key}>
                    <a
                      className={link.primary ? "is-primary" : undefined}
                      href={link.url}
                      target={external ? "_blank" : undefined}
                      rel={external ? "noreferrer" : undefined}
                    >
                      {key === "github" && (
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 16 16"
                          fill="none"
                          aria-hidden="true"
                        >
                          <path
                            d="M5.5 2.5h-2a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-2M8 8l5.5-5.5M10 2.5h3.5V6"
                            stroke="currentColor"
                            strokeWidth="1.25"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                      {t(`footer.project.links.${key}`)}
                    </a>
                  </li>
                );
              })}
            </ul>
          </nav>
        </div>

        <p className="footer-legal">{t("footer.legal")}</p>

        <div className="footer-bottom">
          <span>© 2026 DeID</span>
          <span>{t("footer.bottom")}</span>
        </div>
      </div>
    </footer>
  );
}
