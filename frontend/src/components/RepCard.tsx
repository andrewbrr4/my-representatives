import type { Representative } from "@/types";
import ReactMarkdown from "react-markdown";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

const levelColors: Record<string, string> = {
  federal: "bg-blue-600 text-white hover:bg-blue-700",
  state: "bg-amber-600 text-white hover:bg-amber-700",
  municipal: "bg-emerald-600 text-white hover:bg-emerald-700",
};

interface RepCardProps {
  rep: Representative;
}

export function RepCard({ rep }: RepCardProps) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-start gap-4 space-y-0">
        {rep.photo_url ? (
          <img
            src={rep.photo_url}
            alt={rep.name}
            className="w-16 h-16 rounded-full object-cover border-2 border-muted flex-shrink-0"
          />
        ) : (
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center text-muted-foreground text-xl font-semibold flex-shrink-0">
            {rep.name.charAt(0)}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <CardTitle className="text-lg">{rep.name}</CardTitle>
            <Badge className={levelColors[rep.level] || ""}>
              {rep.level}
            </Badge>
          </div>
          <CardDescription className="mt-1">
            {rep.office}
            {rep.party && ` · ${rep.party}`}
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {rep.summary === undefined ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        ) : rep.summary ? (
          <div className="space-y-2 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none">
            <div>
              <h4 className="font-semibold text-foreground">Background</h4>
              <ReactMarkdown>{rep.summary.background}</ReactMarkdown>
            </div>
            <div>
              <h4 className="font-semibold text-foreground">Policy Positions</h4>
              <ReactMarkdown>{rep.summary.policy_positions}</ReactMarkdown>
            </div>
            <div>
              <h4 className="font-semibold text-foreground">Recent Legislative Record</h4>
              <ul className="list-disc pl-5 space-y-1">
                {rep.summary.recent_legislative_record.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-foreground">Recent Press</h4>
              <ul className="list-disc pl-5 space-y-1">
                {rep.summary.recent_press.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-foreground">Top Donors</h4>
              <ul className="list-disc pl-5 space-y-1">
                {rep.summary.top_donors.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground italic">
            Research unavailable for this representative.
          </p>
        )}

        {/* Contact links */}
        <div className="flex gap-3 text-sm flex-wrap">
          {rep.contact.website && (
            <a
              href={rep.contact.website}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline underline-offset-2 hover:text-primary/80"
            >
              Website
            </a>
          )}
          {rep.contact.phone && (
            <a
              href={`tel:${rep.contact.phone}`}
              className="text-primary underline underline-offset-2 hover:text-primary/80"
            >
              {rep.contact.phone}
            </a>
          )}
          {rep.contact.email && (
            <a
              href={`mailto:${rep.contact.email}`}
              className="text-primary underline underline-offset-2 hover:text-primary/80"
            >
              Email
            </a>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
