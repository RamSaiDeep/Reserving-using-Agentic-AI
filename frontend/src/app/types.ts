export interface ChatMessage {
  role: 'system' | 'user' | 'model' | 'agent' | 'action' | 'error' | 'warn';
  text: string;
  state?: 'analyzing' | '';
  id: string;
}

export interface SummaryData {
  accidentYears: number;
  devPeriods: number;
  oldestAY: number | null;
  latestAY: number | null;
  maxDevAge: number;
  totalPaid: number;
  completeness: number;
  isNewLOB: boolean;
  isLongTail: boolean;
  hasPremium: boolean;
  hasExposure: boolean;
  hasCounts: boolean;
  format: 'wide' | 'long';
  dataType: 'paid' | 'incurred';
  parseLog: string[];
  original_columns?: string[];
  entities?: string[];
  selected_entities?: string[] | null;
  classification?: {
    data_type: string;
    confidence: string;
    is_cas_format: boolean;
  };
  inspection?: {
    is_multi_entity: boolean;
    entity_column: string | null;
    entity_count: number;
    reserving_roles: Record<string, string | null>;
    accumulation_states: Record<string, string | null>;
  };
}

export interface LDFItem {
  fromAge: number;
  toAge: number | string;
  volumeWeighted: number | null;
  straightAvg: number | null;
  weighted3yr: number | null;
  weighted5yr: number | null;
  std: number;
  cov: number;
  n: number;
  isTail: boolean;
}

export interface TriangleData {
  accidentYears: number[];
  devAges: number[];
  matrix: (number | null)[][];
  incurred_matrix: (number | null)[][];
  ldfs: LDFItem[];
  hasPremium: boolean;
}

export interface ModelParam {
  key: string;
  label: string;
  default: any;
}

export interface RankedModel {
  code: string;
  label: string;
  desc: string;
  score: number;
  recommended: boolean;
  params: ModelParam[];
}

export interface ExecuteResult {
  success: boolean;
  results: Record<string, any>[];
  totalIBNR: number;
  totalUlt: number;
  totalPaid: number;
  narration: string;
  cdfs: number[];
  ldfs: number[];
  dev_ages: number[];
  loss_ratios?: {
    accident_year: number;
    premium: number;
    paid_lr_pct: number | null;
    ultimate_lr_pct: number | null;
  }[];
  suggested_elr?: number;
  ldf_stability?: {
    from_age: number;
    to_age: number;
    n: number;
    vw: number | null;
    cov_pct: number | null;
    stability: string;
    credibility: string;
  }[];
  olf_results?: {
    accident_year: number;
    earned_premium: number;
    average_rate_level: number;
    olf: number;
    on_level_premium: number;
  }[];
  volatility?: number;
  error?: string;
}
