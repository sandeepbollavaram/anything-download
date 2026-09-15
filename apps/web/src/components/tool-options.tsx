"use client";

import { Input, Label, NativeSelect } from "@/components/ui/input";
import { copy } from "@/lib/copy";
import type { OptionField } from "@/lib/options";

export function ToolOptions({
  fields,
  values,
  onChange,
}: {
  fields: OptionField[];
  values: Record<string, string | boolean>;
  onChange: (key: string, value: string | boolean) => void;
}) {
  if (fields.length === 0) {
    return null;
  }

  return (
    <fieldset className="space-y-4">
      <legend className="font-medium">{copy.widget.optionsHeading}</legend>
      <div className="grid gap-4 sm:grid-cols-2">
        {fields.map((field) => {
          const id = `opt-${field.key}`;
          if (field.kind === "checkbox") {
            return (
              <div key={field.key} className="flex min-h-11 items-center gap-3 sm:col-span-2">
                <input
                  id={id}
                  type="checkbox"
                  className="border-input size-5 rounded"
                  checked={Boolean(values[field.key])}
                  onChange={(event) => onChange(field.key, event.target.checked)}
                />
                <Label htmlFor={id} className="mb-0">
                  {field.label}
                </Label>
              </div>
            );
          }
          if (field.kind === "select") {
            return (
              <div key={field.key}>
                <Label htmlFor={id}>{field.label}</Label>
                <NativeSelect
                  id={id}
                  value={String(values[field.key] ?? field.defaultValue)}
                  onChange={(event) => onChange(field.key, event.target.value)}
                >
                  {field.options.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </NativeSelect>
              </div>
            );
          }
          if (field.kind === "text") {
            return (
              <div key={field.key} className="sm:col-span-2">
                <Label htmlFor={id}>{field.label}</Label>
                <Input
                  id={id}
                  value={String(values[field.key] ?? "")}
                  placeholder={field.placeholder}
                  onChange={(event) => onChange(field.key, event.target.value)}
                />
              </div>
            );
          }
          return (
            <div key={field.key}>
              <Label htmlFor={id}>{field.label}</Label>
              <Input
                id={id}
                type="number"
                min={field.min}
                max={field.max}
                step={field.step}
                value={String(values[field.key] ?? "")}
                onChange={(event) => onChange(field.key, event.target.value)}
              />
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}
