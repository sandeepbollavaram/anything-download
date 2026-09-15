import { LegalPage } from "@/components/legal-page";
import { copy } from "@/lib/copy";
import { TermsContent } from "@/lib/legal";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: copy.legal.terms.title,
  description: copy.legal.terms.description,
  path: "/terms",
});

export default function TermsPage() {
  return (
    <LegalPage title={copy.legal.terms.title}>
      <TermsContent />
    </LegalPage>
  );
}
