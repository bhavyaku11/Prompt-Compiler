import React from 'react';

interface LogoProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl' | number;
  alt?: string;
}

const sizeClasses = {
  sm: 'h-7 w-7',
  md: 'h-8 w-8',
  lg: 'h-10 w-10',
  xl: 'h-12 w-12',
};

export const Logo: React.FC<LogoProps> = ({
  className = '',
  size = 'md',
  alt = 'Prompt Compiler Logo',
}) => {
  const sizeClass = typeof size === 'string' ? sizeClasses[size] || sizeClasses.md : '';
  const inlineStyle = typeof size === 'number' ? { width: `${size}px`, height: `${size}px` } : undefined;

  return (
    <div
      className={`relative shrink-0 flex items-center justify-center overflow-hidden rounded-xl select-none transition-transform duration-200 group-hover:scale-105 ${sizeClass} ${className}`}
      style={inlineStyle}
    >
      {/* Light Mode Logo (Dark squircle on light background) */}
      <img
        src="/logo-dark.png"
        alt={alt}
        className="h-full w-full object-contain block dark:hidden drop-shadow-xs"
        draggable={false}
      />
      {/* Dark Mode Logo (White squircle on dark background) */}
      <img
        src="/logo-light.png"
        alt={alt}
        className="h-full w-full object-contain hidden dark:block drop-shadow-xs"
        draggable={false}
      />
    </div>
  );
};

export default Logo;
