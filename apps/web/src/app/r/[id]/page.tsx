import { ResultClient } from "@/app/r/[id]/result-client";
import { Container } from "@/components/container";
import { copy } from "@/lib/copy";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: copy.result.heading,
  description: copy.brand.honest,
  path: "/r",
  index: false,
});

export default async function ResultPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="relative isolate -mt-[4.25rem] overflow-hidden pt-[4.25rem]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[34rem]"
      >
        <div className="bg-grid absolute inset-0" />
        <div className="glow-accent animate-aurora absolute -left-40 -top-48 size-[40rem]" />
      </div>
      <Container className="py-10 sm:py-14">
        <ResultClient id={id} />
      </Container>
    </div>
  );
}
