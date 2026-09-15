import { ExtensionPreview } from "@/components/home/extension-section";
import { LegalPage } from "@/components/legal-page";
import { copy } from "@/lib/copy";
import { ExtensionContent } from "@/lib/legal";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: copy.legal.extension.title,
  description: copy.legal.extension.description,
  path: "/extension",
});

export default function ExtensionPage() {
  return (
    <LegalPage
      title={copy.legal.extension.title}
      lead={copy.legal.extension.description}
      heroAside={
        <div className="hidden w-80 lg:block">
          <ExtensionPreview />
        </div>
      }
    >
      <ExtensionContent />
    </LegalPage>
  );
}
