"use client";

import { ArrowRight, Link2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Container } from "@/components/container";
import { Reveal } from "@/components/motion/reveal";
import { Spinner } from "@/components/ui/feedback";
import { copy } from "@/lib/copy";

export function FinalCta() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [pending, setPending] = useState(false);

  return (
    <Container as="section" aria-labelledby="cta-heading" className="pb-8 pt-8 sm:pt-16">
      <Reveal className="bg-brand-gradient text-accent-foreground relative isolate overflow-hidden rounded-[2rem] px-6 py-14 text-center sm:px-12 sm:py-20">
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
          <div className="animate-aurora absolute -left-24 -top-24 size-[30rem] rounded-full bg-white/10 blur-3xl" />
          <div className="animate-aurora absolute -bottom-32 -right-10 size-[26rem] rounded-full bg-[#19c3ff]/25 blur-3xl [animation-delay:-8s]" />
          <div className="absolute inset-0 [background-image:linear-gradient(rgb(255_255_255/0.07)_1px,transparent_1px),linear-gradient(90deg,rgb(255_255_255/0.07)_1px,transparent_1px)] [background-size:44px_44px] [mask-image:radial-gradient(ellipse_60%_70%_at_50%_50%,#000_20%,transparent_100%)]" />
        </div>
        <h2
          id="cta-heading"
          className="font-display text-4xl font-extrabold sm:text-5xl lg:text-6xl"
        >
          {copy.home.ctaTitle}
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-lg opacity-90">{copy.home.ctaLead}</p>
        <form
          className="mx-auto mt-8 flex max-w-2xl flex-col gap-2 rounded-2xl bg-white p-2 shadow-lg sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            if (!url.trim()) return;
            setPending(true);
            router.push(`/analyze?${new URLSearchParams({ url: url.trim() }).toString()}`);
          }}
        >
          <label htmlFor="cta-url" className="sr-only">
            {copy.home.ctaLabel}
          </label>
          <span className="flex min-w-0 flex-1 items-center gap-2 pl-3">
            <Link2 className="size-5 shrink-0 text-[#1450e6]" aria-hidden="true" />
            <input
              id="cta-url"
              type="url"
              inputMode="url"
              required
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://"
              className="min-h-12 w-full min-w-0 bg-transparent text-base text-[#0b1b3a] placeholder:text-[#4a5670] focus-visible:outline-none"
            />
          </span>
          <button
            type="submit"
            className="press font-display inline-flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-xl bg-[#0b1b3a] px-6 text-base font-bold text-white hover:bg-[#13264d] focus-visible:outline-offset-2"
          >
            {pending ? <Spinner /> : null}
            {copy.home.ctaButton}
            {!pending ? <ArrowRight className="size-4" aria-hidden="true" /> : null}
          </button>
        </form>
        <p className="mt-5 text-sm opacity-90">
          Or{" "}
          <Link href="/tools" className="font-bold underline underline-offset-4">
            browse all tools
          </Link>
        </p>
      </Reveal>
    </Container>
  );
}
