import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface CrossLink {
  to: string;
  title: string;
  body: string;
  cta: string;
}

const LINKS: CrossLink[] = [
  {
    to: "/issues",
    title: "Where do they stand on a specific issue?",
    body: "Search any topic — housing, climate, taxes — and we'll find each rep's stance.",
    cta: "Search by issue",
  },
  {
    to: "/elections",
    title: "What's on your ballot?",
    body: "See upcoming elections, polling info, and candidates for your address.",
    cta: "See upcoming elections",
  },
];

export function CrossLinkCards() {
  return (
    <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-4">
      {LINKS.map((link) => (
        <Link
          key={link.to}
          to={link.to}
          className="block group"
        >
          <Card className="h-full transition-colors hover:border-primary group-focus-visible:border-primary">
            <CardHeader>
              <CardTitle className="text-lg font-bold tracking-tight leading-snug">{link.title}</CardTitle>
              <CardDescription className="text-sm leading-relaxed">{link.body}</CardDescription>
            </CardHeader>
            <CardContent>
              <span className="inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wider text-primary group-hover:underline group-focus-visible:underline underline-offset-2">
                {link.cta}
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </span>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}
