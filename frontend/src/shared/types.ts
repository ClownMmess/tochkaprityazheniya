export type Option={id:string;slug:string;label:string};
export type Meta={cities:(Option & {area:string})[];categories:Option[];age_groups:Option[];interests:(Option & {categories:Option[]})[];sources:{label:string;url:string;loaded:boolean}[];organizers:{id:string;label:string}[]};
export type Preferences={home_city:string|null;include_nearby:boolean;age_group_id:string|null;interest_ids:string[];interest_category_ids:string[];organizer_ids:string[];budget_min:number|null;budget_max:number|null};
export type Match={percent:number|null;reasons:string[]};
export type Event={match:Match;available_occurrences:number;genres:{slug:string;label:string}[];id:string;occurrence_id:string;title:string;city:string;city_name:string;starts_at:string|null;kind:"event"|"place";schedule_kind:"session"|"period"|"place";schedule_note:string|null;ends_at:string|null;place_name:string|null;address:string|null;price_min:number|null;price_max:number|null;price_text:string|null;is_free:boolean;age_restriction:number|null;categories:string[];category_name:string;image_url:string|null;status:string;is_demo:boolean;is_tracked:boolean;remind_at:string|null;organizers:{id:string;name:string;external_url:string|null}[];source:{name:string;url:string;updated_at:string|null;fetched_at:string}};
export type EventDetail=Event & {description:string;occurrences:Event[]};
export type Page={items:Event[];page:number;page_size:number;total:number;alternatives?:Alternative[]};
export type Filters={city:string;include_nearby:boolean;party_size:string;budget_total:string;date_from:string;date_to:string;categories:string[];interest_categories:string[];source:string;venue:string;time_of_day:string;price_match:string;sort:string;price_max:string;age_max:string;age_exact:string;kind:string;is_free:boolean;query:string;show_demo:boolean};
export type Intent={city:string;include_nearby?:boolean;date_from?:string|null;date_to?:string|null;time_of_day?:string|null;party_size?:number;budget_total?:number|null;budget_per_person?:number|null;categories?:string[];interest_categories?:string[];organizers?:string[];performers?:string[];excluded_categories?:string[];price_match?:string;age_max?:number|null;age_exact?:number|null;venue_type?:string|null;keywords?:string[];corrected_text?:string|null;free_only?:boolean;hard_constraints?:string[];unparsed_terms?:string[]};
export type SearchResult={total:number;page:number;page_size:number;intent:Intent;results:{event:Event;score:number;reasons:string[]}[];llm_status:string;questions:{question:string;options:{label:string;text:string;intent:Intent}[]}[];relaxations:Alternative[]};
export type Alternative={label:string;explanation:string;estimated_count:number;intent:Intent;events:Event[]};
export type Choice={id:string;title:string;public_token:string;deep_link:string|null;web_link:string;events:{event:Event;votes:number|null}[];my_votes:string[];results_visible:boolean;total_votes:number|null;status:string;expires_at:string};
export type Auth={access_token:string;expires_in:number;user:{id:string;max_user_id:string;first_name:string;onboarding_completed:boolean;home_city:string|null;include_nearby:boolean}};
export type Runtime={demo_mode:boolean;bot_name:string;llm_enabled:boolean;actual_occurrences:Record<string,number>;catalog_version:string;horizon_end:string;refresh_enabled:boolean;refresh_seconds:number;llm_model:string};
export type Notification={id:string;type:string;scheduled_at:string;status:string;event:Event;error_code:string|null};

export type SourceStatus={name:string;url:string;events:number;places:number;last_sync_at:string|null;status:string;last_attempt_at:string|null;error:string|null};

export type Suggestion={label:string;text:string};
export type Discovery={ideas:Suggestion[];highlights:Event[];highlight_label:string};
