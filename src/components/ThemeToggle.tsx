import React from "react";
import { Sun, Moon } from "lucide-react";
import { useTheme } from "../context/ThemeContext";

interface ThemeToggleProps {
  className?: string;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ className = "" }) => {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        toggleTheme();
      }}
      aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
      title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
      className={`p-2 rounded-lg bg-brand-card hover:bg-brand-subtle border border-brand-border text-brand-body hover:text-brand-headline transition-colors duration-150 cursor-pointer shadow-sm active:scale-95 flex items-center justify-center ${className}`}
    >
      {theme === "light" ? (
        <Moon className="w-4 h-4 text-brand-accent transition-transform hover:-rotate-12" />
      ) : (
        <Sun className="w-4 h-4 text-amber-400 transition-transform hover:rotate-45" />
      )}
    </button>
  );
};

export default ThemeToggle;
