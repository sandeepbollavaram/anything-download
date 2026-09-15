import { LegalPage } from "@/components/legal-page";
import { copy } from "@/lib/copy";
import { SecurityContent } from "@/lib/legal";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: copy.legal.security.title,
  description: copy.legal.security.description,
  path: "/security",
});

export default function SecurityPage() {
  return (
    <LegalPage title={copy.legal.security.title}>
      <SecurityContent />
    </LegalPage>
  );
}
