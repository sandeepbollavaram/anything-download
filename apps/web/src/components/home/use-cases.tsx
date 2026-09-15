import { BookOpen, Code2, Microscope, Palette, Smile } from "lucide-react";
import Link from "next/link";

import { Container } from "@/components/container";
import { Reveal } from "@/components/motion/reveal";
import { SectionHeading } from "@/components/page-hero";
import { getCatalogueTool } from "@/lib/catalogue";
import { copy } from "@/lib/copy";

const CASES = [
  {
    icon: Palette,
    title: "Creators",
    body: "Turn your own public clips into audio, GIFs and thumbnails.",
    tools: ["video-to-mp3", "video-to-gif", "video-thumbnail"],
  },
  {
    icon: BookOpen,
    title: "Students",
    body: "Merge lecture PDFs, pull out text, and save public slides.",
    tools: ["pdf-merger", "pdf-to-text", "pdf-downloader"],
  },
  {
    icon: Code2,
    title: "Developers",
    body: "Inspect link metadata, grab favicons, screenshot pages.",
    tools: ["url-metadata", "favicon-downloader", "webpage-screenshot"],
  },
  {
    icon: Microscope,
    title: "Researchers",
    body: "Collect the images and PDFs a public page references.",
    tools: ["website-image-gallery", "website-pdf-finder", "url-analyzer"],
  },
  {
    icon: Smile,
    title: "Everyone else",
    body: "Shrink photos, convert formats, make a QR code.",
    tools: ["image-compressor", "image-converter", "qr-generator"],
  },
];

export function UseCases() {
  return (
    <Container as="section" aria-labelledby="usecases-heading" className="py-16 sm:py-24">
      <SectionHeading
        id="usecases-heading"
        eyebrow={copy.home.useCasesEyebrow}
        title={copy.home.useCasesTitle}
      />
      <ul className="scrollbar-none -mx-4 mt-12 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-2 md:mx-0 md:grid md:grid-cols-2 md:overflow-visible md:px-0 xl:grid-cols-5">
        {CASES.map((item, index) => (
          <Reveal
            as="li"
            key={item.title}
            index={index}
            className="surface group flex w-[17rem] shrink-0 snap-start flex-col rounded-2xl p-5 md:w-auto"
          >
            <span
              aria-hidden="true"
              className="bg-accent-soft text-accent mb-4 grid size-11 place-items-center rounded-xl transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110"
            >
              <item.icon className="size-5" />
            </span>
            <h3 className="font-display text-lg font-bold">{item.title}</h3>
            <p className="text-muted-foreground mt-1 flex-1 text-sm">{item.body}</p>
            <ul className="border-border mt-4 space-y-0.5 border-t pt-3">
              {item.tools.map((id) => {
                const tool = getCatalogueTool(id);
                return tool ? (
                  <li key={id}>
                    <Link
                      href={`/tools/${id}`}
                      className="text-link inline-flex min-h-9 items-center text-sm font-semibold"
                    >
                      <span className="underline-grow">{tool.name}</span>
                    </Link>
                  </li>
                ) : null;
              })}
            </ul>
          </Reveal>
        ))}
      </ul>
    </Container>
  );
}
