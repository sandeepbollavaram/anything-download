import { SITE_NAME, SITE_URL } from "@/lib/env";

export function AboutContent() {
  return (
    <>
      <p>
        {SITE_NAME} is a free, privacy-first web utility for analyzing publicly accessible URLs and
        processing files you upload. The positioning is simple: free tools for the open web. No ads.
        No account. No nonsense.
      </p>
      <p>
        You can download and process publicly accessible files and media you have permission to use.
        The service inspects what a source actually exposes, then runs the operation you choose:
        convert, compress, extract, or save a public file.
      </p>
      <p>
        This is not a bypass tool. It will not log in as you, break DRM, skip paywalls, or reach
        private hosts. If a source is unsupported or restricted, you will see that clearly and no
        download is offered.
      </p>
      <p>
        Results are temporary. Files are deleted automatically after a short time, or immediately if
        you choose Delete now.
      </p>
    </>
  );
}

export function PrivacyContent() {
  return (
    <>
      <p>
        {SITE_NAME} does not require an account and does not show advertisements. This instance is
        operated at {SITE_URL}.
      </p>
      <h2>What we receive</h2>
      <p>
        When you paste a URL, that URL is sent to the API so it can be validated and fetched. When
        you upload a file, the file bytes are stored temporarily so a tool can run. We do not ask
        for your name, email, or payment details.
      </p>
      <h2>How long files stay</h2>
      <p>
        Uploads and job results expire and are deleted automatically. You can delete a result sooner
        with Delete now. Do not use this service as storage.
      </p>
      <h2>Logs and abuse prevention</h2>
      <p>
        The server may keep short-lived operational logs such as request times, error codes, and
        network addresses in order to rate-limit abuse. These logs are not used for advertising and
        are not sold.
      </p>
      <h2>Cookies and analytics</h2>
      <p>
        This site uses a theme preference in your browser when you choose a color scheme. It does
        not set advertising cookies and does not embed third-party analytics trackers.
      </p>
      <h2>Browser extension</h2>
      <p>
        The optional Chrome extension sends the address of the page you are on only when you choose
        an action, and nothing else. See <a href="/extension">Chrome extension</a> for the exact
        permissions and data.
      </p>
      <h2>Your rights</h2>
      <p>
        Because there is no account, there is no profile to export. Once a job expires or is
        deleted, the file is gone from this service. If you operate your own instance, you are
        responsible for that instance&apos;s data practices.
      </p>
    </>
  );
}

export function TermsContent() {
  return (
    <>
      <p>
        By using {SITE_NAME} you agree to these terms. The software is provided under the MIT
        License, without warranty of any kind.
      </p>
      <h2>Acceptable use</h2>
      <p>
        You may only submit URLs and files that you are allowed to access and process. You must not
        use the service to attack other systems, to reach internal or loopback addresses, or to
        obtain content that is private, licensed against such use, or protected by DRM or a login.
      </p>
      <h2>No guarantee</h2>
      <p>
        Tools can fail when a source is unreachable, a file is corrupt, a format is unavailable, or
        a server limit is reached. Progress percentages are shown only when the backend reports real
        progress. The service may be rate-limited or unavailable.
      </p>
      <h2>Temporary results</h2>
      <p>
        Output files are temporary. Download them while they exist. The operator may delete data
        earlier to control storage or abuse.
      </p>
      <h2>Your responsibility</h2>
      <p>
        You are responsible for the legality of what you submit and how you use the output. The
        operators of this instance are not liable for loss of files, downtime, or misuse.
      </p>
    </>
  );
}

export function CopyrightContent() {
  return (
    <>
      <p>
        {SITE_NAME} processes files and public URLs on demand. It is not a hosting platform and does
        not keep a public library of other people&apos;s media.
      </p>
      <p>
        You must have permission to download or transform the material you submit. Publicly
        reachable is not the same as free to copy. Respect the rights of authors, performers, and
        publishers.
      </p>
      <h2>What this service will not do</h2>
      <ul>
        <li>Bypass authentication, DRM, paywalls, or license checks.</li>
        <li>Fetch resources on private networks or loopback addresses.</li>
        <li>Keep results after the automatic deletion window.</li>
      </ul>
      <h2>Infringement notices</h2>
      <p>
        If you believe material processed through this instance infringes your copyright, contact
        the operator using the details on the Contact page. Include the job identifier if you have
        one, the URL or filename concerned, and a statement of your rights. Repeat or abusive
        submissions may be blocked.
      </p>
    </>
  );
}

export function SecurityContent() {
  return (
    <>
      <p>
        {SITE_NAME} is designed as a bounded utility: it validates URLs, refuses private targets,
        limits file sizes, and deletes temporary data.
      </p>
      <h2>What we try to prevent</h2>
      <ul>
        <li>Requests to internal, link-local, or loopback addresses.</li>
        <li>Oversized uploads and downloads.</li>
        <li>Password-protected PDFs and DRM-protected media.</li>
        <li>Long-term retention of user files.</li>
      </ul>
      <h2>What you should assume</h2>
      <p>
        Do not upload secrets, private keys, or documents you cannot afford to expose. Transport
        security depends on how this instance is deployed. Treat results as confidential only for as
        long as you keep the download link, and delete them when you are done.
      </p>
      <h2>Reporting a vulnerability</h2>
      <p>
        If you find a security issue, use the Contact page. Please include enough detail to
        reproduce the problem and avoid accessing other people&apos;s data while testing.
      </p>
    </>
  );
}

export function ContactContent() {
  return (
    <>
      <p>
        This website does not include a message form that pretends to send mail. There is no inbox
        behind a submit button on this page.
      </p>
      <p>
        For copyright notices, security reports, or questions about this instance, contact the
        operator of {SITE_URL}. If you run your own copy of the software, you are that operator.
      </p>
      <p>
        Include a short description of the issue, the page or tool involved, and a job identifier
        when you have one. Do not send files that contain passwords or private keys.
      </p>
    </>
  );
}

export function ExtensionContent() {
  return (
    <>
      <p>
        The {SITE_NAME} Chrome extension is an optional companion to this website. It analyzes the
        page you are on with the same public API the website uses, then hands you over to the
        website to process anything. It is not a separate downloader: every address still goes
        through the server&apos;s checks, and the website works fully without it.
      </p>

      <h2>What it does</h2>
      <ul>
        <li>
          <strong>Popup:</strong> shows the page you are on and, when you choose{" "}
          <em>Analyze this page</em>, lists the public images, videos, audio and PDFs the server
          found.
        </li>
        <li>
          <strong>Right-click menu:</strong> Analyze this page, Find images, Find videos, Find
          audio, Find PDFs, and Open in {SITE_NAME}.
        </li>
        <li>
          <strong>Honest results:</strong> when the server reports that content is private, needs a
          login, is DRM protected, is region restricted, is unsupported, or that you are being rate
          limited, the extension shows exactly that. It never shows a download button for something
          the server did not allow.
        </li>
      </ul>

      <h2>Permissions it uses</h2>
      <ul>
        <li>
          <strong>activeTab</strong>: read the address of the current tab, only after you click the
          extension or use its menu, and only for that tab.
        </li>
        <li>
          <strong>contextMenus</strong>: add the {SITE_NAME} entries to the right-click menu.
        </li>
        <li>
          <strong>storage</strong>: remember your theme and server choice in this browser, and pass
          a menu request to the popup for a few seconds.
        </li>
        <li>
          <strong>Access to {SITE_URL}</strong>: send the page address to the {SITE_NAME} API. If
          you run your own server, the extension asks for access to that one address only.
        </li>
      </ul>
      <p>
        It does not request access to all websites, your tabs list, history, cookies, downloads, or
        the ability to read or change pages. It contains no remote code.
      </p>

      <h2>What it sends</h2>
      <p>
        The address of the page you are on, and only when you choose an action. The request carries
        no cookies or other credentials.
      </p>

      <h2>What it never collects</h2>
      <ul>
        <li>Browsing history, page content, or form data.</li>
        <li>Cookies, passwords, session tokens or account details.</li>
        <li>Analytics, advertising identifiers, or usage tracking.</li>
      </ul>

      <h2>What it will not do</h2>
      <p>
        Like the website, it only works with publicly accessible content you are authorized to use.
        It does not bypass logins, paywalls, DRM, CAPTCHAs, region restrictions or any other access
        control, and it cannot reach private or local network addresses; the server refuses them.
      </p>

      <h2>Installing</h2>
      <p>
        The extension is not yet listed on the Chrome Web Store. Until it is, developers can load it
        from the source repository: open <code>chrome://extensions</code>, enable Developer mode,
        choose <em>Load unpacked</em>, and select <code>apps/extension/src</code>.
      </p>
    </>
  );
}
