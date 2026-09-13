import { Link } from "@tanstack/react-router";
import { motion } from "motion/react";
import { Bell, Settings, ScanEye } from "lucide-react";

export function Header() {
  return (
    <motion.header
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="sticky top-0 z-50 border-b border-border/80 bg-card/95 backdrop-blur-sm"
    >
      <div className="mx-auto flex h-14 max-w-[1340px] items-center gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex min-w-0 items-center gap-2.5">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-brand/10 text-brand ring-1 ring-brand/20">
            <ScanEye className="h-[18px] w-[18px]" strokeWidth={1.9} />
          </span>
          <span className="min-w-0 leading-none">
            <span className="block truncate text-[15px] font-bold tracking-tight text-ink">
              SafeVision <span className="text-brand">AI</span>
            </span>
            <span className="mt-1 hidden text-[9px] font-semibold tracking-[0.18em] text-muted-foreground uppercase sm:block">
              Safety Intelligence Platform
            </span>
          </span>
        </Link>

        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          <span className="hidden items-center gap-2 rounded-full border border-border bg-secondary/70 px-3 py-1.5 md:inline-flex">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-online opacity-70" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-online" />
            </span>
            <span className="micro-label text-muted-foreground">AI Systems Online</span>
          </span>

          <button
            type="button"
            aria-label="Notifications"
            className="relative hidden h-9 w-9 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-ink sm:grid"
          >
            <Bell className="h-[17px] w-[17px]" strokeWidth={1.8} />
            <span className="absolute top-0.5 right-0.5 grid h-[15px] min-w-[15px] place-items-center rounded-full bg-alert px-[3px] text-[9px] leading-none font-bold text-primary-foreground">
              3
            </span>
          </button>
          <button
            type="button"
            aria-label="Settings"
            className="hidden h-9 w-9 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-ink sm:grid"
          >
            <Settings className="h-[17px] w-[17px]" strokeWidth={1.8} />
          </button>

          <Link
            to="/login"
            className="group relative inline-flex h-9 shrink-0 items-center justify-center overflow-hidden rounded-md bg-ink px-5 text-[13px] font-semibold tracking-wide text-primary-foreground shadow-card transition-all duration-300 hover:bg-brand hover:shadow-lift"
          >
            <span className="relative z-10">Login</span>
          </Link>
        </div>
      </div>
    </motion.header>
  );
}
