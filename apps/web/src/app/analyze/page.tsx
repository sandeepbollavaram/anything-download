import { Suspense } from "react";

import { AnalyzeClient } from "@/app/analyze/analyze-client";
import { Container } from "@/components/container";
import { Skeleton } from "@/components/ui/feedback";
import { copy } from "@/lib/copy";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Analyze",
  description: copy.brand.honest,
  path: "/analyze",
  index: false,
});

export default function AnalyzePage() {
  return (
    <Suspense
      fallback={
        <Container className="space-y-6 py-14">
          <p className="sr-only">{copy.a11y.loading}</p>
          <Skeleton className="h-12 w-72" />
          <Skeleton className="h-64 w-full rounded-3xl" />
        </Container>
      }
    >
      <AnalyzeClient />
    </Suspense>
  );
}
