import { Compass } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { copy } from "@/lib/copy";

export default function NotFound() {
  return (
    <EmptyState
      icon={Compass}
      code="404"
      title={copy.errors.notFound}
      lead={copy.errors.notFoundLead}
    >
      <Button asChild>
        <Link href="/">{copy.result.backHome}</Link>
      </Button>
      <Button asChild variant="outline">
        <Link href="/tools">{copy.home.allTools}</Link>
      </Button>
    </EmptyState>
  );
}
