import React, { useEffect } from "react";
import { motion } from "framer-motion";
import { ThemeToggle } from "../components/ThemeToggle";

interface SplashProps {
  onFinish: () => void;
  duration?: number;
}

export const Splash: React.FC<SplashProps> = ({ onFinish, duration = 1800 }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onFinish();
    }, duration);

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't auto-advance on Tab or theme toggle keyboard events
      if (e.key === "Tab") return;
      onFinish();
    };
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      clearTimeout(timer);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onFinish, duration]);

  return (
    <div
      onClick={onFinish}
      className="fixed inset-0 w-screen h-screen bg-brand-bg text-brand-headline flex flex-col items-center justify-center cursor-pointer select-none z-50 transition-colors duration-200"
    >
      {/* Top-Right Theme Toggle */}
      <div
        className="absolute top-6 right-6 z-20"
        onClick={(e) => e.stopPropagation()}
      >
        <ThemeToggle />
      </div>

      {/* Centered Minimal Brand Identity */}
      <motion.div
        className="flex flex-col items-center text-center px-6"
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
      >
        {/* Crisp Monogram Icon */}
        <div className="w-14 h-14 rounded-xl bg-brand-accent text-brand-accent-text flex items-center justify-center text-2xl font-bold tracking-tight mb-5 shadow-card transition-colors duration-200">
          A
        </div>

        {/* Brand Headline */}
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-brand-headline transition-colors duration-200">
          Autonoma
        </h1>

        <p className="text-sm font-medium text-brand-body mt-2 tracking-wide transition-colors duration-200">
          Autonomous AI Product Company
        </p>

        {/* Minimal Progress Line */}
        <div className="w-24 h-1 bg-brand-border rounded-full mt-8 overflow-hidden transition-colors duration-200">
          <motion.div
            className="h-full bg-brand-accent rounded-full"
            initial={{ width: 0 }}
            animate={{ width: "100%" }}
            transition={{ duration: duration / 1000, ease: "easeInOut" }}
          />
        </div>
      </motion.div>

      {/* Subtle Hint */}
      <p className="absolute bottom-8 text-xs text-brand-body font-medium opacity-70 transition-colors duration-200">
        Click anywhere to continue
      </p>
    </div>
  );
};

export default Splash;
