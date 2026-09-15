import { LegalPage } from "@/components/legal-page";
import { copy } from "@/lib/copy";
import { AboutContent } from "@/lib/legal";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: copy.legal.about.title,
  description: copy.legal.about.description,
  path: "/about",
});

export default function AboutPage() {
  return (
    <LegalPage title={copy.legal.about.title}>
      <AboutContent />
    </LegalPage>
  );
}
