#pragma once
#include <cmath>
#ifdef __CUDACC__
#define PT_HD __host__ __device__
#else
#define PT_HD
#endif

// Forward derivatives of the exact discrete RK4 computation, not a different ODE solver.
struct Dual {
    double value = 0.0;
    double d[7] = {};
    PT_HD Dual(double v = 0.0) : value(v) {}
};
PT_HD inline Dual operator+(const Dual& a, const Dual& b) {
    Dual c(a.value + b.value);
    for (int j=0;j<7;++j) c.d[j]=a.d[j]+b.d[j];
    return c;
}
PT_HD inline Dual operator-(const Dual& a, const Dual& b) {
    Dual c(a.value - b.value);
    for (int j=0;j<7;++j) c.d[j]=a.d[j]-b.d[j];
    return c;
}
PT_HD inline Dual operator*(const Dual& a, const Dual& b) {
    Dual c(a.value * b.value);
    for (int j=0;j<7;++j) c.d[j]=a.d[j]*b.value+a.value*b.d[j];
    return c;
}
PT_HD inline Dual dual_sqrt(const Dual& a) {
    Dual c(sqrt(a.value));
    if (c.value>0.0) for(int j=0;j<7;++j) c.d[j]=a.d[j]/(2.0*c.value);
    return c;
}
PT_HD inline void dynamics(const Dual* state, const Dual& drag, const double* wind, Dual* out) {
    Dual rel[3];
    for(int j=0;j<3;++j) rel[j]=state[j+3]-Dual(wind[j]);
    Dual speed=dual_sqrt(rel[0]*rel[0]+rel[1]*rel[1]+rel[2]*rel[2]);
    for(int j=0;j<3;++j) {
        out[j]=state[j+3];
        out[j+3]=Dual(j==1 ? -32.174 : 0.0)-drag*speed*rel[j];
    }
}
PT_HD inline void rk4(Dual* state, double h, const Dual& drag, const double* wind) {
    Dual a[6],b[6],c[6],d[6],temp[6];
    dynamics(state,drag,wind,a);
    for(int j=0;j<6;++j) temp[j]=state[j]+Dual(0.5*h)*a[j];
    dynamics(temp,drag,wind,b);
    for(int j=0;j<6;++j) temp[j]=state[j]+Dual(0.5*h)*b[j];
    dynamics(temp,drag,wind,c);
    for(int j=0;j<6;++j) temp[j]=state[j]+Dual(h)*c[j];
    dynamics(temp,drag,wind,d);
    for(int j=0;j<6;++j) state[j]=state[j]+Dual(h/6.0)*(a[j]+Dual(2.0)*b[j]+Dual(2.0)*c[j]+d[j]);
}
PT_HD inline void evaluate_fit(const double* parameters, const double* times, const double* positions,
                              const double* weights, const double* wind, int n,
                              double k0,double sigma,bool prior,double* residual,double* jacobian) {
    Dual state[6];
    for(int j=0;j<6;++j) { state[j]=Dual(parameters[j]); state[j].d[j]=1.0; }
    Dual drag(parameters[6]); drag.d[6]=1.0;
    double current=0.0;
    for(int i=0;i<n;++i) {
        double delta=times[i]-current;
        if(times[i]>0.0) {
            int steps=static_cast<int>(delta/0.002); if(steps<1) steps=1;
            double h=delta/steps;
            for(int s=0;s<steps;++s) rk4(state,h,drag,wind);
            current=times[i];
        }
        for(int j=0;j<3;++j) {
            Dual r;
            for(int axis=0;axis<3;++axis) r=r+Dual(weights[i*9+j*3+axis])*(state[axis]-Dual(positions[i*3+axis]));
            residual[i*3+j]=r.value;
            for(int p=0;p<7;++p) jacobian[(i*3+j)*7+p]=r.d[p];
        }
    }
    if(prior) {
        residual[n*3]=(parameters[6]-k0)/sigma;
        for(int p=0;p<7;++p) jacobian[n*3*7+p]=p==6 ? 1.0/sigma : 0.0;
    }
}
