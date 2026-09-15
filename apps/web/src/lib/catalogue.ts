export type ToolCategory = "video" | "image" | "pdf" | "audio" | "web" | "utility";

export type CatalogueTool = {
  id: string;
  name: string;
  category: ToolCategory;
  group: "video" | "image" | "pdf" | "audio" | "web";
  short: string;
  description: string;
  howItWorks: string[];
  accepts: string[];
  willNot: string[];
  inputs: Array<"url" | "upload" | "uploads" | "text">;
  popular?: boolean;
};

const sharedWillNot = [
  "It will not bypass DRM, logins, paywalls, or other access controls.",
  "It will not process private, authenticated, or geo-blocked sources.",
  "It will not keep your files after the automatic deletion window.",
];

export const TOOL_CATALOGUE: CatalogueTool[] = [
  {
    id: "video-downloader",
    name: "Video downloader",
    category: "video",
    group: "video",
    short: "Save a publicly reachable video file or public platform rendition.",
    description:
      "Fetches a video that is already publicly accessible (a direct file URL or a public platform listing) and gives you the file the source actually exposes.",
    howItWorks: [
      "Paste a public video URL.",
      "We inspect the source and list the formats it advertises.",
      "You pick a format and we fetch that file. The result is deleted automatically.",
    ],
    accepts: ["Public direct video URLs", "Public pages on supported platforms"],
    willNot: sharedWillNot,
    inputs: ["url"],
    popular: true,
  },
  {
    id: "video-to-mp3",
    name: "Video to MP3",
    category: "video",
    group: "video",
    short: "Extract the audio track from a public video as MP3.",
    description:
      "Takes a public video URL or an uploaded video/audio file and extracts the first audio track as an MP3.",
    howItWorks: [
      "Paste a public video URL or upload a video file.",
      "Choose a bitrate if you want something other than the default.",
      "We extract the audio track. No video is kept in the result.",
    ],
    accepts: ["Public video URLs", "Uploaded video or audio files that contain an audio track"],
    willNot: [...sharedWillNot, "It will not invent an audio track if the source has none."],
    inputs: ["url", "upload"],
    popular: true,
  },
  {
    id: "video-to-wav",
    name: "Video to WAV",
    category: "video",
    group: "video",
    short: "Extract the audio track from a public video as WAV.",
    description:
      "Extracts the first audio track from a public video or uploaded media file and writes an uncompressed WAV.",
    howItWorks: [
      "Provide a public video URL or upload a file with an audio track.",
      "We decode the audio and write a PCM WAV file.",
    ],
    accepts: ["Public video URLs", "Uploaded video or audio files"],
    willNot: sharedWillNot,
    inputs: ["url", "upload"],
  },
  {
    id: "video-to-mp4",
    name: "Video to MP4",
    category: "video",
    group: "video",
    short: "Convert a public video to MP4.",
    description:
      "Converts a public video URL or uploaded video into an MP4. Compatible streams may be remuxed without re-encoding.",
    howItWorks: [
      "Paste a public video URL or upload a video.",
      "Choose a quality preset.",
      "We write an MP4 and delete it after a short time.",
    ],
    accepts: ["Public video URLs", "Uploaded video files"],
    willNot: sharedWillNot,
    inputs: ["url", "upload"],
    popular: true,
  },
  {
    id: "video-compressor",
    name: "Video compressor",
    category: "video",
    group: "video",
    short: "Re-encode a public video to a smaller MP4.",
    description:
      "Re-encodes a public or uploaded video with a chosen compression level. The output may not always be smaller than the source.",
    howItWorks: [
      "Provide a public video URL or upload a video.",
      "Choose a light, medium, or strong compression level.",
      "We re-encode to MP4. If the result is not smaller, we say so.",
    ],
    accepts: ["Public video URLs", "Uploaded video files"],
    willNot: [...sharedWillNot, "It will not promise a smaller file in every case."],
    inputs: ["url", "upload"],
    popular: true,
  },
  {
    id: "video-to-gif",
    name: "Video to GIF",
    category: "video",
    group: "video",
    short: "Turn a short clip of a public video into a GIF.",
    description:
      "Renders a short segment of a public or uploaded video as an animated GIF. Duration is capped to keep files reasonable.",
    howItWorks: [
      "Provide a public video URL or upload a video.",
      "Set start time, duration, frame rate, and width.",
      "We render that clip as a GIF.",
    ],
    accepts: ["Public video URLs", "Uploaded video files"],
    willNot: [...sharedWillNot, "It will not render long videos as GIFs."],
    inputs: ["url", "upload"],
  },
  {
    id: "video-thumbnail",
    name: "Video thumbnail",
    category: "video",
    group: "video",
    short: "Capture a still frame from a public video.",
    description: "Extracts a single frame from a public or uploaded video as JPEG, PNG, or WebP.",
    howItWorks: [
      "Provide a public video URL or upload a video.",
      "Optionally set a timestamp and output format.",
      "We extract one frame. The default timestamp is 10% into the video.",
    ],
    accepts: ["Public video URLs", "Uploaded video files"],
    willNot: sharedWillNot,
    inputs: ["url", "upload"],
  },
  {
    id: "video-metadata",
    name: "Video metadata",
    category: "video",
    group: "video",
    short: "Read technical metadata from a public video.",
    description:
      "Probes a public or uploaded video and returns streams, duration, codecs, and size. No file is produced.",
    howItWorks: [
      "Provide a public video URL or upload a video.",
      "We inspect the file and return the metadata we can read.",
    ],
    accepts: ["Public video URLs", "Uploaded video files"],
    willNot: [...sharedWillNot, "It will not alter or strip metadata from the source."],
    inputs: ["url", "upload"],
  },
  {
    id: "image-downloader",
    name: "Image downloader",
    category: "image",
    group: "image",
    short: "Save a publicly reachable image.",
    description:
      "Fetches a direct, publicly accessible image URL and returns the file the server actually sent.",
    howItWorks: [
      "Paste a public image URL.",
      "We fetch the file and make it available for a short time.",
    ],
    accepts: ["Public direct image URLs"],
    willNot: sharedWillNot,
    inputs: ["url"],
  },
  {
    id: "image-compressor",
    name: "Image compressor",
    category: "image",
    group: "image",
    short: "Reduce the size of a public or uploaded image.",
    description:
      "Re-encodes a public or uploaded image. You can choose quality and whether to keep metadata.",
    howItWorks: [
      "Paste an image URL or upload an image.",
      "Choose quality and whether to keep metadata.",
      "We write a compressed file. If it is not smaller, we say so.",
    ],
    accepts: ["Public image URLs", "Uploaded raster images (not SVG)"],
    willNot: [...sharedWillNot, "It will not process SVG files."],
    inputs: ["url", "upload"],
    popular: true,
  },
  {
    id: "image-converter",
    name: "Image converter",
    category: "image",
    group: "image",
    short: "Convert an image to JPEG, PNG, WebP, AVIF, and more.",
    description: "Converts a public or uploaded raster image to another common format.",
    howItWorks: [
      "Provide an image URL or upload an image.",
      "Choose the target format and quality.",
      "We encode the image in that format.",
    ],
    accepts: ["Public image URLs", "Uploaded raster images"],
    willNot: [...sharedWillNot, "It will not convert SVG artwork."],
    inputs: ["url", "upload"],
    popular: true,
  },
  {
    id: "image-resizer",
    name: "Image resizer",
    category: "image",
    group: "image",
    short: "Resize a public or uploaded image.",
    description:
      "Scales a raster image by width, height, or percent, with contain, cover, or exact fit.",
    howItWorks: [
      "Provide an image URL or upload an image.",
      "Set a percent or explicit dimensions and a fit mode.",
      "We write a resized copy.",
    ],
    accepts: ["Public image URLs", "Uploaded raster images"],
    willNot: sharedWillNot,
    inputs: ["url", "upload"],
    popular: true,
  },
  {
    id: "image-to-webp",
    name: "Image to WebP",
    category: "image",
    group: "image",
    short: "Convert a public or uploaded image to WebP.",
    description:
      "Encodes a raster image as WebP, with optional lossless mode and metadata control.",
    howItWorks: [
      "Provide an image URL or upload an image.",
      "Choose quality or lossless encoding.",
      "We write a WebP file.",
    ],
    accepts: ["Public image URLs", "Uploaded raster images"],
    willNot: sharedWillNot,
    inputs: ["url", "upload"],
    popular: true,
  },
  {
    id: "image-to-pdf",
    name: "Image to PDF",
    category: "image",
    group: "image",
    short: "Place one or more images into a PDF.",
    description:
      "Builds a PDF from one or more public or uploaded images. Page size can fit the image or use A4/Letter.",
    howItWorks: [
      "Upload one or more images, or provide an image URL.",
      "Choose a page size.",
      "We write a PDF. Multiple images become multiple pages.",
    ],
    accepts: ["Public image URLs", "One or more uploaded raster images"],
    willNot: sharedWillNot,
    inputs: ["url", "upload", "uploads"],
  },
  {
    id: "pdf-downloader",
    name: "PDF downloader",
    category: "pdf",
    group: "pdf",
    short: "Save a publicly reachable PDF.",
    description: "Fetches a direct, publicly accessible PDF URL and returns that file.",
    howItWorks: ["Paste a public PDF URL.", "We fetch the file and make it available briefly."],
    accepts: ["Public direct PDF URLs"],
    willNot: sharedWillNot,
    inputs: ["url"],
  },
  {
    id: "pdf-compressor",
    name: "PDF compressor",
    category: "pdf",
    group: "pdf",
    short: "Recompress images inside a PDF.",
    description:
      "Opens a public or uploaded PDF and recompresses large raster images. Encrypted PDFs are rejected.",
    howItWorks: [
      "Provide a public PDF URL or upload a PDF.",
      "Choose a compression level.",
      "We rewrite the PDF. If it is not smaller, we say so.",
    ],
    accepts: ["Public PDF URLs", "Uploaded, unencrypted PDFs"],
    willNot: [...sharedWillNot, "It will not open password-protected or encrypted PDFs."],
    inputs: ["url", "upload"],
    popular: true,
  },
  {
    id: "pdf-merger",
    name: "PDF merger",
    category: "pdf",
    group: "pdf",
    short: "Combine two or more uploaded PDFs.",
    description: "Merges at least two uploaded, unencrypted PDFs into one document.",
    howItWorks: [
      "Upload two or more PDF files.",
      "We concatenate their pages in the order you selected.",
    ],
    accepts: ["Two or more uploaded, unencrypted PDFs"],
    willNot: [...sharedWillNot, "It will not merge password-protected PDFs."],
    inputs: ["uploads"],
    popular: true,
  },
  {
    id: "pdf-splitter",
    name: "PDF splitter",
    category: "pdf",
    group: "pdf",
    short: "Extract pages or split a PDF into parts.",
    description:
      "Splits a public or uploaded PDF by page ranges, into single pages, or into chunks of a given size.",
    howItWorks: [
      "Provide a public PDF URL or upload a PDF.",
      "Choose ranges, each page, or fixed-size chunks.",
      "One part is returned as a PDF; several parts are zipped.",
    ],
    accepts: ["Public PDF URLs", "Uploaded, unencrypted PDFs"],
    willNot: sharedWillNot,
    inputs: ["url", "upload"],
    popular: true,
  },
  {
    id: "pdf-to-text",
    name: "PDF to text",
    category: "pdf",
    group: "pdf",
    short: "Extract the text layer from a PDF.",
    description:
      "Reads the existing text layer of a public or uploaded PDF. It does not perform optical character recognition.",
    howItWorks: [
      "Provide a public PDF URL or upload a PDF.",
      "Optionally limit the page range.",
      "We write a UTF-8 text file from the text layer.",
    ],
    accepts: ["Public PDF URLs", "Uploaded, unencrypted PDFs"],
    willNot: [...sharedWillNot, "It will not OCR scanned pages that have no text layer."],
    inputs: ["url", "upload"],
  },
  {
    id: "pdf-to-images",
    name: "PDF to images",
    category: "pdf",
    group: "pdf",
    short: "Render PDF pages as images.",
    description:
      "Renders selected pages of a public or uploaded PDF as PNG, JPEG, or WebP. Multiple pages are returned as a ZIP.",
    howItWorks: [
      "Provide a public PDF URL or upload a PDF.",
      "Choose format, DPI, and optional page ranges.",
      "One page is an image; several pages are zipped.",
    ],
    accepts: ["Public PDF URLs", "Uploaded, unencrypted PDFs"],
    willNot: sharedWillNot,
    inputs: ["url", "upload"],
    popular: true,
  },
  {
    id: "url-to-pdf",
    name: "URL to PDF",
    category: "pdf",
    group: "pdf",
    short: "Render a public webpage as a PDF.",
    description:
      "Opens a publicly reachable webpage in a headless browser and prints it to PDF. It does not log in or bypass paywalls.",
    howItWorks: [
      "Paste a public webpage URL.",
      "Choose page size, orientation, and whether to print backgrounds.",
      "We render the page as it is publicly served.",
    ],
    accepts: ["Public webpage URLs"],
    willNot: sharedWillNot,
    inputs: ["url"],
  },
  {
    id: "audio-downloader",
    name: "Audio downloader",
    category: "audio",
    group: "audio",
    short: "Save a publicly reachable audio file or public platform audio.",
    description:
      "Fetches a public audio file or an audio rendition advertised by a supported public platform.",
    howItWorks: [
      "Paste a public audio URL.",
      "We inspect advertised formats and fetch the one you select.",
    ],
    accepts: ["Public direct audio URLs", "Public pages on supported platforms"],
    willNot: sharedWillNot,
    inputs: ["url"],
    popular: true,
  },
  {
    id: "audio-converter",
    name: "Audio converter",
    category: "audio",
    group: "audio",
    short: "Convert public or uploaded audio to MP3, WAV, AAC, and more.",
    description:
      "Converts a public or uploaded audio (or video-with-audio) file to a chosen audio format.",
    howItWorks: [
      "Provide a public URL or upload a file with an audio track.",
      "Choose a target format and bitrate for lossy formats.",
      "We write the converted file.",
    ],
    accepts: ["Public audio or video URLs", "Uploaded audio or video files"],
    willNot: sharedWillNot,
    inputs: ["url", "upload"],
    popular: true,
  },
  {
    id: "audio-compressor",
    name: "Audio compressor",
    category: "audio",
    group: "audio",
    short: "Re-encode audio at a lower bitrate.",
    description:
      "Re-encodes public or uploaded audio at a chosen compression level. The output may not always be smaller.",
    howItWorks: [
      "Provide a public URL or upload a file with an audio track.",
      "Choose a compression level.",
      "We re-encode and report if the result is not smaller.",
    ],
    accepts: ["Public audio or video URLs", "Uploaded audio or video files"],
    willNot: sharedWillNot,
    inputs: ["url", "upload"],
  },
  {
    id: "audio-metadata",
    name: "Audio metadata",
    category: "audio",
    group: "audio",
    short: "Read technical metadata from an audio file.",
    description:
      "Probes a public or uploaded audio file and returns streams, duration, and tags we can read.",
    howItWorks: [
      "Provide a public audio URL or upload an audio file.",
      "We inspect the file and return metadata. No new media file is produced.",
    ],
    accepts: ["Public audio URLs", "Uploaded audio files"],
    willNot: sharedWillNot,
    inputs: ["url", "upload"],
  },
  {
    id: "url-analyzer",
    name: "URL analyzer",
    category: "web",
    group: "web",
    short: "Inspect a public URL and see which operations apply.",
    description:
      "Normalizes a URL, follows public redirects, and reports what kind of source it is and which tools can run on it.",
    howItWorks: [
      "Paste a URL.",
      "We validate it, fetch public headers or a public page, and return the analysis.",
    ],
    accepts: ["Any URL this service is willing to fetch"],
    willNot: sharedWillNot,
    inputs: ["url"],
    popular: true,
  },
  {
    id: "webpage-resource-extractor",
    name: "Webpage resource extractor",
    category: "web",
    group: "web",
    short: "List publicly referenced files on a webpage.",
    description:
      "Fetches a public HTML page and lists images, video, audio, PDFs, and other resources the markup already references.",
    howItWorks: [
      "Paste a public webpage URL.",
      "We parse the HTML and return the public URLs it already contains.",
    ],
    accepts: ["Public webpage URLs"],
    willNot: [...sharedWillNot, "It will not execute scripts to discover hidden resources."],
    inputs: ["url"],
  },
  {
    id: "image-url-extractor",
    name: "Image URL extractor",
    category: "web",
    group: "web",
    short: "List image URLs referenced by a public page.",
    description:
      "Finds image URLs that a public webpage already references in markup and metadata.",
    howItWorks: ["Paste a public webpage URL.", "We return the image URLs present on the page."],
    accepts: ["Public webpage URLs"],
    willNot: sharedWillNot,
    inputs: ["url"],
  },
  {
    id: "website-image-gallery",
    name: "Website image gallery",
    category: "web",
    group: "web",
    short: "Download publicly referenced images from a page into a ZIP.",
    description:
      "Collects images a public page already links to and packs the ones we can fetch into a ZIP archive.",
    howItWorks: [
      "Paste a public webpage URL.",
      "We fetch a bounded number of publicly referenced images.",
      "Successfully downloaded images are zipped. Skipped images are listed.",
    ],
    accepts: ["Public webpage URLs"],
    willNot: sharedWillNot,
    inputs: ["url"],
    popular: true,
  },
  {
    id: "website-pdf-finder",
    name: "Website PDF finder",
    category: "web",
    group: "web",
    short: "Find PDF links on a public webpage.",
    description: "Lists PDF and document URLs that a public page already references.",
    howItWorks: [
      "Paste a public webpage URL.",
      "We return the document links present in the markup.",
    ],
    accepts: ["Public webpage URLs"],
    willNot: sharedWillNot,
    inputs: ["url"],
  },
  {
    id: "website-video-finder",
    name: "Website video finder",
    category: "web",
    group: "web",
    short: "Find video URLs referenced by a public page.",
    description: "Lists video URLs that a public webpage already references.",
    howItWorks: ["Paste a public webpage URL.", "We return the video links present in the markup."],
    accepts: ["Public webpage URLs"],
    willNot: sharedWillNot,
    inputs: ["url"],
  },
  {
    id: "website-audio-finder",
    name: "Website audio finder",
    category: "web",
    group: "web",
    short: "Find audio URLs referenced by a public page.",
    description: "Lists audio URLs that a public webpage already references.",
    howItWorks: ["Paste a public webpage URL.", "We return the audio links present in the markup."],
    accepts: ["Public webpage URLs"],
    willNot: sharedWillNot,
    inputs: ["url"],
  },
  {
    id: "url-metadata",
    name: "URL metadata",
    category: "utility",
    group: "web",
    short: "Read title, description, and social tags from a public page.",
    description:
      "Fetches a public webpage and returns title, description, canonical URL, and other metadata the page already publishes.",
    howItWorks: [
      "Paste a public webpage URL.",
      "We read the document head and return the metadata we find.",
    ],
    accepts: ["Public webpage URLs"],
    willNot: sharedWillNot,
    inputs: ["url"],
  },
  {
    id: "favicon-downloader",
    name: "Favicon downloader",
    category: "utility",
    group: "web",
    short: "Download a site’s publicly advertised favicon.",
    description:
      "Looks for favicon links on a public page, then tries the conventional /favicon.ico path.",
    howItWorks: [
      "Paste a public website URL.",
      "We try the icons the page advertises, then a standard favicon path.",
    ],
    accepts: ["Public website URLs"],
    willNot: sharedWillNot,
    inputs: ["url"],
  },
  {
    id: "qr-generator",
    name: "QR generator",
    category: "utility",
    group: "web",
    short: "Create a QR code from text or a URL.",
    description:
      "Encodes text you provide as a PNG or SVG QR code. Nothing is fetched from the encoded URL.",
    howItWorks: [
      "Enter the text or URL to encode.",
      "Choose format, scale, border, and error correction.",
      "We generate the code from your text only.",
    ],
    accepts: ["Plain text or a URL you type in (up to 2,000 characters)"],
    willNot: [
      "It will not fetch or verify the encoded URL.",
      "It will not keep your text after the result expires.",
    ],
    inputs: ["text"],
    popular: true,
  },
  {
    id: "qr-reader",
    name: "QR reader",
    category: "utility",
    group: "web",
    short: "Read QR codes and barcodes from an image.",
    description:
      "Scans a public or uploaded raster image for QR codes and barcodes and returns the decoded text.",
    howItWorks: [
      "Paste an image URL or upload a raster image.",
      "We scan the image and return any codes we detect.",
    ],
    accepts: ["Public image URLs", "Uploaded raster images (not SVG)"],
    willNot: [...sharedWillNot, "It will not scan SVG files."],
    inputs: ["url", "upload"],
  },
  {
    id: "webpage-screenshot",
    name: "Webpage screenshot",
    category: "utility",
    group: "web",
    short: "Capture a screenshot of a public webpage.",
    description:
      "Opens a publicly reachable page in a headless browser and captures a PNG. It does not log in or dismiss consent walls.",
    howItWorks: [
      "Paste a public webpage URL.",
      "Set viewport size and whether to capture the full page.",
      "We render the page as it is publicly served.",
    ],
    accepts: ["Public webpage URLs"],
    willNot: sharedWillNot,
    inputs: ["url"],
  },
  {
    id: "file-downloader",
    name: "File downloader",
    category: "utility",
    group: "web",
    short: "Save a publicly reachable document or archive.",
    description:
      "Fetches a direct public file that is not a typical video, image, audio, or PDF, for example a document or archive.",
    howItWorks: [
      "Paste a public direct file URL.",
      "We fetch the file if the server allows anonymous access.",
    ],
    accepts: ["Public direct document or archive URLs"],
    willNot: sharedWillNot,
    inputs: ["url"],
  },
];

export const TOOL_IDS = TOOL_CATALOGUE.map((tool) => tool.id);

export function getCatalogueTool(id: string): CatalogueTool | undefined {
  return TOOL_CATALOGUE.find((tool) => tool.id === id);
}

export function toolsByGroup() {
  const groups: Record<CatalogueTool["group"], CatalogueTool[]> = {
    video: [],
    image: [],
    pdf: [],
    audio: [],
    web: [],
  };
  for (const tool of TOOL_CATALOGUE) {
    groups[tool.group].push(tool);
  }
  return groups;
}

export function popularToolsByGroup() {
  const groups = toolsByGroup();
  return {
    video: groups.video.filter((tool) => tool.popular),
    image: groups.image.filter((tool) => tool.popular),
    pdf: groups.pdf.filter((tool) => tool.popular),
    audio: groups.audio.filter((tool) => tool.popular),
    web: groups.web.filter((tool) => tool.popular),
  };
}

export function toolsNotNeedingSource(currentId?: string): CatalogueTool[] {
  return TOOL_CATALOGUE.filter(
    (tool) =>
      tool.id !== currentId &&
      (tool.inputs.includes("text") ||
        tool.inputs.includes("upload") ||
        tool.inputs.includes("uploads")),
  ).slice(0, 8);
}
