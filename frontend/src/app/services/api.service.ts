import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface BaselineResponse {
  id: number;
  image_path: string;
  shelf_capacity: number;
  message: string;
}

export interface AuditResponse {
  id: number;
  compliance_score: number;
  fill_rate: number;
  report_path: string;
  visual_report_path: string;
  comparison_report: any;
  message: string;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private hostname = window.location.hostname;
  private apiUrl = `http://${this.hostname}:3000/api`;
  public baseUrl = `http://${this.hostname}:3000`; // For fetching images

  constructor(private http: HttpClient) { }

  uploadBaseline(file: File, name: string): Observable<BaselineResponse> {
    const formData = new FormData();
    formData.append('image', file);
    formData.append('name', name);
    return this.http.post<BaselineResponse>(`${this.apiUrl}/baseline/upload`, formData);
  }

  uploadAudit(file: File, baselineId: number, name: string): Observable<AuditResponse> {
    const formData = new FormData();
    formData.append('image', file);
    formData.append('baselineId', baselineId.toString());
    formData.append('name', name);
    return this.http.post<AuditResponse>(`${this.apiUrl}/audit/compare`, formData);
  }

  getBaselines(): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/baselines`);
  }

  getAudits(): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/audits`);
  }

  deleteBaseline(id: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/baseline/${id}`);
  }

  deleteAudit(id: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/audit/${id}`);
  }
}
