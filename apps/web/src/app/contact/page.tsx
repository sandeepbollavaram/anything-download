import { LegalPage } from "@/components/legal-page";
import { copy } from "@/lib/copy";
import { ContactContent } from "@/lib/legal";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: copy.legal.contact.title,
  description: copy.legal.contact.description,
  path: "/contact",
});

export default function ContactPage() {
  return (
    <LegalPage title={copy.legal.contact.title}>
      <ContactContent />
    </LegalPage>
  );
}
