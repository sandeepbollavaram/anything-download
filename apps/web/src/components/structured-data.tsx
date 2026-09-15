import { humanizeKey } from "@/lib/format";

export function StructuredData({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      {Object.entries(data).map(([key, value]) => (
        <DataNode key={key} label={humanizeKey(key)} value={value} />
      ))}
    </div>
  );
}

function DataNode({ label, value }: { label: string; value: unknown }) {
  if (value == null || value === "") {
    return null;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return null;
    }
    const primitive = value.every(
      (item) => item == null || ["string", "number", "boolean"].includes(typeof item),
    );
    return (
      <div>
        <p className="text-muted-foreground text-sm font-medium">{label}</p>
        {primitive ? (
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
            {value.map((item, index) => (
              <li key={index} className="break-words">
                {String(item)}
              </li>
            ))}
          </ul>
        ) : (
          <ul className="mt-2 space-y-3">
            {value.map((item, index) => (
              <li key={index} className="bg-muted rounded-lg p-3">
                {item && typeof item === "object" && !Array.isArray(item) ? (
                  <StructuredData data={item as Record<string, unknown>} />
                ) : (
                  <span className="break-words text-sm">{String(item)}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }
  if (typeof value === "object") {
    return (
      <div>
        <p className="text-muted-foreground text-sm font-medium">{label}</p>
        <div className="mt-2 border-l pl-3">
          <StructuredData data={value as Record<string, unknown>} />
        </div>
      </div>
    );
  }
  return (
    <div className="border-border grid gap-1 border-b pb-2 text-sm last:border-0 sm:grid-cols-[12rem_1fr]">
      <span className="text-muted-foreground">{label}</span>
      <span className="break-words font-medium">
        {typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}
      </span>
    </div>
  );
}
