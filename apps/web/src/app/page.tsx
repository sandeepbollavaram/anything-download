import { Container } from "@/components/container";
import { Ecosystem } from "@/components/home/ecosystem";
import { ExtensionSection } from "@/components/home/extension-section";
import { FinalCta } from "@/components/home/final-cta";
import { Hero } from "@/components/home/hero";
import { HowItWorks } from "@/components/home/how-it-works";
import { ProductDemo } from "@/components/home/product-demo";
import { QuickActions } from "@/components/home/quick-actions";
import { Trust } from "@/components/home/trust";
import { UseCases } from "@/components/home/use-cases";
import { SectionHeading } from "@/components/page-hero";
import { ToolExplorer } from "@/components/tool-explorer";
import { TOOL_CATALOGUE } from "@/lib/catalogue";
import { copy } from "@/lib/copy";

/*
 * Rhythm: full-width visual (hero) → wide content (quick actions) → interactive (how it works)
 * → wide bento (ecosystem) → full-width band (demo) → full-width dark band (trust)
 * → feature panel (extension) → use cases → interactive discovery → final CTA.
 */
export default function HomePage() {
  return (
    <>
      <Hero />
      <QuickActions />
      <HowItWorks />
      <Ecosystem />
      <ProductDemo />
      <Trust />
      <ExtensionSection />
      <UseCases />
      <section
        aria-labelledby="discovery-heading"
        className="bg-background-alt/70 border-border border-y"
      >
        <Container className="space-y-10 py-16 sm:py-24">
          <SectionHeading
            id="discovery-heading"
            eyebrow={copy.home.discoveryEyebrow}
            title={copy.home.discoveryTitle}
            lead={copy.home.discoveryLead}
          />
          <ToolExplorer tools={TOOL_CATALOGUE} limit={8} headingLevel="h3" idPrefix="home" />
        </Container>
      </section>
      <FinalCta />
    </>
  );
}
