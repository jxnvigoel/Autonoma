import React, { useEffect, useState } from "react";
import { Loader2, LogOut, X } from "lucide-react";
import { AccountUser, apiGetProfile, apiUpdateProfile } from "../lib/auth";

interface ProfileModalProps {
  onClose: () => void;
  onLogout: () => void;
  onUpdated: (user: AccountUser) => void;
}

export const ProfileModal: React.FC<ProfileModalProps> = ({ onClose, onLogout, onUpdated }) => {
  const [profile, setProfile] = useState<AccountUser | null>(null);
  const [form, setForm] = useState({ name: "", title: "", organization: "" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    apiGetProfile()
      .then((p) => {
        setProfile(p);
        setForm({ name: p.name, title: p.title || "", organization: p.organization || "" });
      })
      .catch((e) => setMessage(e instanceof Error ? e.message : String(e)));
  }, []);

  const save = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const p = await apiUpdateProfile(form);
      setProfile(p);
      onUpdated(p);
      setMessage("Profile saved.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const input = "w-full rounded-lg border border-brand-border bg-brand-bg px-3 py-2 text-sm text-brand-headline";
  const initials = (profile?.name || "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={onClose}>
      <div
        role="dialog"
        aria-label="Profile"
        className="w-full max-w-sm rounded-2xl border border-brand-border bg-brand-card p-5 space-y-4 text-brand-headline"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-brand-accent text-brand-accent-text flex items-center justify-center font-bold">
              {initials}
            </div>
            <div>
              <p className="text-sm font-bold">{profile?.name || "Profile"}</p>
              <p className="text-[11px] text-brand-body">{profile?.email}</p>
            </div>
          </div>
          <button type="button" onClick={onClose} className="p-1 rounded hover:bg-brand-subtle cursor-pointer" aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>

        {profile && (
          <p className="text-[11px] text-brand-muted">
            Signs in with {profile.auth_method === "google" ? "Google" : "email and password"} · member since{" "}
            {new Date(profile.created_at).toLocaleDateString()} · {profile.project_count ?? 0} project(s)
          </p>
        )}

        {(["name", "title", "organization"] as const).map((field) => (
          <label key={field} className="block space-y-1">
            <span className="text-[11px] font-medium text-brand-body capitalize">{field === "title" ? "Job title" : field}</span>
            <input
              className={input}
              value={form[field]}
              onChange={(e) => setForm({ ...form, [field]: e.target.value })}
              maxLength={120}
            />
          </label>
        ))}

        {message && <p className="text-[11px] text-brand-body">{message}</p>}

        <div className="flex items-center justify-between pt-1">
          <button
            type="button"
            onClick={onLogout}
            className="flex items-center gap-1.5 text-xs font-medium text-red-600 hover:underline cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" /> Log out
          </button>
          <button
            type="button"
            onClick={save}
            disabled={busy || !form.name.trim()}
            className="flex items-center gap-1.5 rounded-lg bg-brand-accent text-brand-accent-text px-3 py-1.5 text-xs font-semibold disabled:opacity-50 cursor-pointer"
          >
            {busy && <Loader2 className="w-3.5 h-3.5 animate-spin" />} Save
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProfileModal;
