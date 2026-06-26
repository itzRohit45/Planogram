import { Injectable } from '@angular/core';
import { AuditResponse } from './api.service';

@Injectable({
  providedIn: 'root'
})
export class SharedDataService {
  public currentReport: AuditResponse | null = null;
  public currentBaseline: any = null;
}
