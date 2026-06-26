import { ComponentFixture, TestBed } from '@angular/core/testing';

import { BaselineUploadComponent } from './baseline-upload.component';

describe('BaselineUploadComponent', () => {
  let component: BaselineUploadComponent;
  let fixture: ComponentFixture<BaselineUploadComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BaselineUploadComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(BaselineUploadComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
