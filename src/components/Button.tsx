import React from "react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  isLoading?: boolean;
  variant?: "primary" | "secondary" | "outline";
}

export const Button: React.FC<ButtonProps> = ({
  children,
  isLoading = false,
  variant = "primary",
  disabled,
  className = "",
  ...props
}) => {
  const baseClasses =
    "inline-flex items-center justify-center font-semibold rounded-lg text-sm px-4 py-2.5 transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-accent focus:ring-offset-brand-bg disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shadow-sm";

  const variantClasses = {
    primary:
      "bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text active:scale-[0.98]",
    secondary:
      "bg-brand-card hover:bg-brand-subtle text-brand-headline border border-brand-border active:scale-[0.98]",
    outline:
      "bg-transparent hover:bg-brand-subtle text-brand-headline border border-brand-border active:scale-[0.98]",
  }[variant];

  return (
    <button
      disabled={disabled || isLoading}
      className={`${baseClasses} ${variantClasses} ${className}`}
      {...props}
    >
      {isLoading && (
        <svg
          className="animate-spin -ml-1 mr-2 h-4 w-4 text-current"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      )}
      {children}
    </button>
  );
};

export default Button;
