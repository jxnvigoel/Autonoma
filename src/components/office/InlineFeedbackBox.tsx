import React, { useEffect, useRef, useState } from "react";
import { Loader2, Send, X } from "lucide-react";

/**
 * In-page replacement for window.prompt(), which Electron does not support (it returns null,
 * so buttons that relied on it silently did nothing).
 */
export const InlineFeedbackBox: React.FC<{
  label: string;
  placeholder?: string;
  initialValue?: string;
  submitLabel?: string;
  onSubmit: (text: string) => Promise<void> | void;
  onCancel: () => void;
}> = ({ label, placeholder, initialValue = "", submitLabel = "Send", onSubmit, onCancel }) => {
  const [text, setText] = useState(initialValue);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    ref.current?.focus();
  }, []);

  const submit = async () => {
    const value = text.trim();
    if (!value || busy) return;
    setBusy(true);
    try {
      await onSubmit(value);
      onCancel();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2 p-2.5 rounded-lg border border-brand-border bg-brand-card space-y-2">
      <label className="block text-[11px] font-semibold text-brand-headline">{label}</label>
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
          if (e.key === "Escape") onCancel();
        }}
        placeholder={placeholder}
        rows={4}
        className="w-full resize-y rounded-md border border-brand-border bg-brand-subtle px-2 py-1.5 text-xs text-brand-headline focus:outline-none focus:ring-1 focus:ring-purple-500"
      />
      <div className="flex items-center justify-end gap-2">
        <span className="mr-auto text-[10px] text-brand-body">⌘/Ctrl + Enter to send · Esc to cancel</span>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="px-2.5 py-1 rounded-md border border-brand-border text-[11px] font-medium cursor-pointer flex items-center gap-1 disabled:opacity-50"
        >
          <X className="w-3 h-3" /> Cancel
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={busy || !text.trim()}
          className="px-2.5 py-1 rounded-md bg-purple-600 hover:bg-purple-500 text-white text-[11px] font-semibold cursor-pointer flex items-center gap-1 disabled:opacity-50"
        >
          {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />} {submitLabel}
        </button>
      </div>
    </div>
  );
};
