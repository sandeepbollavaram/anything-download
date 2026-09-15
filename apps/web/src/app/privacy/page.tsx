import { LegalPage } from "@/components/legal-page";
import { copy } from "@/lib/copy";
import { PrivacyContent } from "@/lib/legal";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: copy.legal.privacy.title,
  description: copy.legal.privacy.description,
  path: "/privacy",
});

export default function PrivacyPage() {
  return (
    <LegalPage title={copy.legal.privacy.title}>
      <PrivacyContent />
    </LegalPage>
  );
}
