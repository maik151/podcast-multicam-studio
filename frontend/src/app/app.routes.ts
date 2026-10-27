import { Routes } from '@angular/router';
import { DirectorComponent } from './features/director/director.component';
import { MobileCamComponent } from './features/mobile-cam/mobile-cam.component';

export const routes: Routes = [
  { path: '', component: DirectorComponent },
  { path: 'cam/:id', component: MobileCamComponent },
  { path: '**', redirectTo: '' }
];
