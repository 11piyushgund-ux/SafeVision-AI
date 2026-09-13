import { createFileRoute } from "@tanstack/react-router";
import { Header } from "@/components/site/Header";
import { HeroModules } from "@/components/site/HeroModules";
import { HowItWorks } from "@/components/site/HowItWorks";
import { ImpactInAction } from "@/components/site/ImpactInAction";
import { BiggerPicture } from "@/components/site/BiggerPicture";

const title = "SafeVision AI — Safety Intelligence for Modern Manufacturing";
const description =
  "Monitor, detect, assess, and respond to workplace safety events through one intelligent command platform built for modern manufacturing.";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <div className="min-h-screen bg-canvas">
      <Header />
      <main>
        <HeroModules />
        <HowItWorks />
        <ImpactInAction />
        <BiggerPicture />
      </main>
    </div>
  );
}
