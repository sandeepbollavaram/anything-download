"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { copy } from "@/lib/copy";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <EmptyState
      icon={AlertTriangle}
      title={copy.errors.generic}
      lead="Nothing you did caused this. Your files are unaffected."
    >
      <Button type="button" onClick={reset}>
        <RotateCcw />
        {copy.widget.retry}
      </Button>
      <Button asChild variant="outline">
        <Link href="/">{copy.result.backHome}</Link>
      </Button>
    </EmptyState>
  );
}
