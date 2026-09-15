import { WifiOff } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { copy } from "@/lib/copy";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: copy.offline.title,
  description: copy.offline.description,
  path: "/offline",
  index: false,
});

export default function OfflinePage() {
  return (
    <EmptyState icon={WifiOff} title={copy.offline.title} lead={copy.offline.description}>
      <Button asChild variant="outline">
        <Link href="/">{copy.offline.back}</Link>
      </Button>
    </EmptyState>
  );
}
