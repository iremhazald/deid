import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { projectLinks } from "../../config/project";

function isExternal(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

/** Lightweight compact footer for upload/review/export workflow pages. */
export function UploadFooter() {
  const { t } = useTranslation();
  const configured = useMemo(() => projectLinks(), []);

  return (
    <footer className="upload-footer">
      <span className="upload-footer-brand">DeID</span>
      <span className="upload-footer-sep" aria-hidden="true">·</span>
      <span className="upload-footer-tagline">
        {t("footer.metadata.openSource")} · {t("footer.metadata.local")} · {t("footer.metadata.api")}
      </span>
      {configured.length > 0 && (
        <>
          <span className="upload-footer-sep" aria-hidden="true">·</span>
          <nav className="upload-footer-links" aria-label={t("footer.project.title")}>
            {configured.map((link, i) => {
              const external = isExternal(link.url);
              return (
                <span key={link.key}>
                  {i > 0 && <span aria-hidden="true"> · </span>}
                  <a
                    href={link.url}
                    target={external ? "_blank" : undefined}
                    rel={external ? "noreferrer" : undefined}
                  >
                    {t(`footer.project.links.${link.key}`)}
                  </a>
                </span>
              );
            })}
          </nav>
        </>
      )}
    </footer>
  );
}
