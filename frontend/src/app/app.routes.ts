import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'dashboard', loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent) },
  { path: 'baseline', loadComponent: () => import('./features/baseline-upload/baseline-upload.component').then(m => m.BaselineUploadComponent) },
  { path: 'audit', loadComponent: () => import('./features/audit-upload/audit-upload.component').then(m => m.AuditUploadComponent) },
  { path: 'catalog', loadComponent: () => import('./features/catalog/catalog.component').then(m => m.CatalogComponent) },
  { path: 'report', loadComponent: () => import('./features/compliance-report/compliance-report.component').then(m => m.ComplianceReportComponent) },
  { path: 'report/:id', loadComponent: () => import('./features/compliance-report/compliance-report.component').then(m => m.ComplianceReportComponent) },
  { path: '**', redirectTo: 'dashboard' }
];
