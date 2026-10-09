import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  FileCheck,
  ArrowRight,
  Loader2,
  Sparkles,
  Users,
  Calendar,
  DollarSign,
  Layers,
  AlertCircle,
} from "lucide-react";
import { IntakeFormData } from "../../lib/engine";

interface IntakeFormProps {
  onSubmit: (data: IntakeFormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
}

export const IntakeForm: React.FC<IntakeFormProps> = ({
  onSubmit,
  isLoading = false,
  error = null,
}) => {
  const [formData, setFormData] = useState<IntakeFormData>({
    projectName: "",
    description: "",
    targetUsers: "",
    timeline: "",
    budget: "",
  });

  const [validationError, setValidationError] = useState<string | null>(null);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (validationError) {
      setValidationError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.projectName.trim()) {
      setValidationError("Please enter a project name.");
      return;
    }
    if (!formData.description.trim()) {
      setValidationError("Please describe what you are trying to build.");
      return;
    }
    if (!formData.targetUsers.trim()) {
      setValidationError("Please specify who will use this application.");
      return;
    }
    if (!formData.timeline.trim()) {
      setValidationError("Please enter your target timeline (e.g. 6 weeks).");
      return;
    }
    if (!formData.budget.trim()) {
      setValidationError(
        "Please enter your budget and expected monthly running costs."
      );
      return;
    }

    try {
      await onSubmit(formData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setValidationError(msg);
    }
  };

  const activeError = validationError || error;

  return (
    <div className="min-h-full flex-1 flex flex-col items-center justify-center p-4 sm:p-6 md:p-8 bg-brand-bg text-brand-headline transition-colors duration-200">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="w-full max-w-2xl bg-brand-card border border-brand-border rounded-2xl shadow-card p-6 sm:p-8 space-y-6 transition-colors duration-200"
      >
        {/* Header / Intro */}
        <div className="space-y-2 border-b border-brand-border/70 pb-5">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-brand-accent text-brand-accent-text flex items-center justify-center shadow-xs">
              <FileCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold tracking-tight text-brand-headline">
                  Project Intake
                </h2>
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-brand-subtle text-brand-accent border border-brand-border">
                  Step 01 • BA Discovery
                </span>
              </div>
              <p className="text-xs text-brand-body">
                Fill in these core details to brief your Business Analyst before the discovery session begins.
              </p>
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {activeError && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="p-3.5 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2.5 shadow-xs"
          >
            <AlertCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
            <span className="leading-relaxed">{activeError}</span>
          </motion.div>
        )}

        {/* Form Fields */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Field 1: Project Name */}
          <div className="space-y-1.5">
            <label
              htmlFor="projectName"
              className="text-xs font-semibold text-brand-headline flex items-center gap-1.5"
            >
              <Layers className="w-3.5 h-3.5 text-brand-accent" />
              <span>Project Name</span>
              <span className="text-rose-500 text-xs">*</span>
            </label>
            <input
              id="projectName"
              name="projectName"
              type="text"
              required
              disabled={isLoading}
              value={formData.projectName}
              onChange={handleChange}
              placeholder="e.g. TaskFlow Pro, Local Artisan Marketplace"
              className="w-full px-3.5 py-2.5 rounded-xl bg-brand-bg border border-brand-border focus:border-brand-accent focus:outline-none text-xs text-brand-headline placeholder:text-brand-body/50 transition-colors shadow-inner"
            />
          </div>

          {/* Field 2: What are you trying to build? */}
          <div className="space-y-1.5">
            <label
              htmlFor="description"
              className="text-xs font-semibold text-brand-headline flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5 text-brand-accent" />
              <span>In a sentence or two, what are you trying to build?</span>
              <span className="text-rose-500 text-xs">*</span>
            </label>
            <textarea
              id="description"
              name="description"
              required
              rows={3}
              disabled={isLoading}
              value={formData.description}
              onChange={handleChange}
              placeholder="e.g. A fast web platform for freelance designers to send interactive invoices, collect client feedback, and track payments without paying high platform fees."
              className="w-full px-3.5 py-2.5 rounded-xl bg-brand-bg border border-brand-border focus:border-brand-accent focus:outline-none text-xs text-brand-headline placeholder:text-brand-body/50 transition-colors resize-none shadow-inner leading-relaxed"
            />
          </div>

          {/* Field 3: Who will use it? */}
          <div className="space-y-1.5">
            <label
              htmlFor="targetUsers"
              className="text-xs font-semibold text-brand-headline flex items-center gap-1.5"
            >
              <Users className="w-3.5 h-3.5 text-brand-accent" />
              <span>Who will use it?</span>
              <span className="text-rose-500 text-xs">*</span>
            </label>
            <input
              id="targetUsers"
              name="targetUsers"
              type="text"
              required
              disabled={isLoading}
              value={formData.targetUsers}
              onChange={handleChange}
              placeholder="e.g. Solo freelancers, creative studios, and their direct clients"
              className="w-full px-3.5 py-2.5 rounded-xl bg-brand-bg border border-brand-border focus:border-brand-accent focus:outline-none text-xs text-brand-headline placeholder:text-brand-body/50 transition-colors shadow-inner"
            />
          </div>

          {/* 2-Column Row for Timeline and Budget */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Field 4: Target Timeline */}
            <div className="space-y-1.5">
              <label
                htmlFor="timeline"
                className="text-xs font-semibold text-brand-headline flex items-center gap-1.5"
              >
                <Calendar className="w-3.5 h-3.5 text-brand-accent" />
                <span>Target timeline</span>
                <span className="text-rose-500 text-xs">*</span>
              </label>
              <input
                id="timeline"
                name="timeline"
                type="text"
                required
                disabled={isLoading}
                value={formData.timeline}
                onChange={handleChange}
                placeholder="e.g. 6 weeks for MVP"
                className="w-full px-3.5 py-2.5 rounded-xl bg-brand-bg border border-brand-border focus:border-brand-accent focus:outline-none text-xs text-brand-headline placeholder:text-brand-body/50 transition-colors shadow-inner"
              />
            </div>

            {/* Field 5: Budget */}
            <div className="space-y-1.5">
              <label
                htmlFor="budget"
                className="text-xs font-semibold text-brand-headline flex items-center gap-1.5"
              >
                <DollarSign className="w-3.5 h-3.5 text-brand-accent" />
                <span>Budget & running costs</span>
                <span className="text-rose-500 text-xs">*</span>
              </label>
              <input
                id="budget"
                name="budget"
                type="text"
                required
                disabled={isLoading}
                value={formData.budget}
                onChange={handleChange}
                placeholder="e.g. $5,000 build, under $50/mo hosting"
                className="w-full px-3.5 py-2.5 rounded-xl bg-brand-bg border border-brand-border focus:border-brand-accent focus:outline-none text-xs text-brand-headline placeholder:text-brand-body/50 transition-colors shadow-inner"
              />
            </div>
          </div>

          {/* Submit Button */}
          <div className="pt-3 flex items-center justify-end">
            <button
              type="submit"
              disabled={isLoading}
              className="w-full sm:w-auto px-6 py-3 rounded-xl bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text text-xs font-semibold shadow-sm flex items-center justify-center gap-2 active:scale-95 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Connecting with Business Analyst...</span>
                </>
              ) : (
                <>
                  <span>Start with my BA</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
};

export default IntakeForm;
