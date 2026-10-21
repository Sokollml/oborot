// Короткие имена для типов, сгенерированных из OpenAPI (src/api/schema.d.ts — не править руками,
// пересоздать: npm run gen:api).
import type { components } from './schema';

type S = components['schemas'];

export type User = S['UserOut'];
export type Meta = S['MetaOut'];
export type Product = S['ProductOut'];
export type ProductOption = S['ProductOption'];
export type RecommendResult = S['RecommendOut'];
export type CompanyLookup = S['CompanyLookupOut'];
export type Application = S['ApplicationOut'];
export type ApplicationListItem = S['ApplicationListItem'];
export type ApplicationPatch = S['ApplicationPatch'];
export type HistoryItem = S['HistoryItem'];
export type Decision = S['DecisionOut'];
export type DocumentRequest = S['DocumentRequestOut'];
export type NotificationsResponse = S['NotificationsOut'];
export type AppStatus = Application['status'];
export type Purpose = S['RecommendIn']['purpose'];
export type QueueItem = S['QueueItem'];
export type AnalystCard = S['AnalystApplicationOut'];
export type CheckOut = S['CheckOut'];
export type ScoringOut = S['ScoringOut'];
export type FactorOut = S['FactorOut'];
export type Recommendation = S['RecommendationOut'];
export type AnalystDecisionIn = S['AnalystDecisionIn'];
export type MyCompany = S['MyCompanyOut'];
export type Potential = S['PotentialOut'];
export type Message = S['MessageOut'];
