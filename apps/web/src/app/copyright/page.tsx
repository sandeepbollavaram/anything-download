import { LegalPage } from "@/components/legal-page";
import { copy } from "@/lib/copy";
import { CopyrightContent } from "@/lib/legal";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: copy.legal.copyright.title,
  description: copy.legal.copyright.description,
  path: "/copyright",
});

export default function CopyrightPage() {
  return (
    <LegalPage title={copy.legal.copyright.title}>
      <CopyrightContent />
    </LegalPage>
  );
}
