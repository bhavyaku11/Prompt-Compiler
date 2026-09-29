import React, { useState } from 'react';

interface UserAvatarProps {
  imageUrl?: string | null;
  name?: string | null;
  email?: string | null;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

const sizeClasses = {
  sm: 'h-7 w-7 text-[11px]',
  md: 'h-8 w-8 text-xs',
  lg: 'h-9 w-9 text-sm',
};

export const UserAvatar: React.FC<UserAvatarProps> = ({
  imageUrl,
  name,
  email,
  className = '',
  size = 'md',
}) => {
  const [candidateIndex, setCandidateIndex] = useState(0);

  // Build ordered list of avatar candidate URLs
  const username = email ? email.split('@')[0].trim() : '';
  const candidateUrls: string[] = [];

  if (imageUrl && imageUrl.trim()) {
    candidateUrls.push(imageUrl.trim());
  }
  if (username) {
    candidateUrls.push(`https://unavatar.io/github/${encodeURIComponent(username)}?fallback=false`);
  }
  if (email && email.trim()) {
    candidateUrls.push(`https://unavatar.io/${encodeURIComponent(email.trim())}?fallback=false`);
  }

  // Reset candidate index if imageUrl or email prop updates
  React.useEffect(() => {
    setCandidateIndex(0);
  }, [imageUrl, email]);

  const currentUrl = candidateIndex < candidateUrls.length ? candidateUrls[candidateIndex] : null;

  const initial = (name?.[0] || email?.[0] || 'U').toUpperCase();
  const dimensionClass = sizeClasses[size] || sizeClasses.md;

  if (currentUrl) {
    return (
      <img
        src={currentUrl}
        alt={name || email || 'User Profile'}
        onError={() => setCandidateIndex((prev) => prev + 1)}
        className={`${dimensionClass} rounded-full object-cover border border-border shrink-0 select-none shadow-2xs ${className}`}
        referrerPolicy="no-referrer"
        crossOrigin="anonymous"
      />
    );
  }

  return (
    <div
      className={`${dimensionClass} rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold font-mono shrink-0 border border-primary/20 select-none shadow-2xs ${className}`}
    >
      {initial}
    </div>
  );
};

export default UserAvatar;
