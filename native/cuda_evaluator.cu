#include <cuda_runtime.h>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "kernel.hpp"
#include <memory>
#include <stdexcept>
#include <string>
namespace py=pybind11;
using Array=py::array_t<double,py::array::c_style|py::array::forcecast>;
inline void checked(cudaError_t code) {
    if(code!=cudaSuccess) throw std::runtime_error(std::string("CUDA: ")+cudaGetErrorString(code));
}
struct Buffer {
    double* data=nullptr;
    size_t count=0;
    explicit Buffer(size_t n):count(n) { checked(cudaMalloc(reinterpret_cast<void**>(&data),n*sizeof(double))); }
    ~Buffer() { if(data) cudaFree(data); }
    Buffer(const Buffer&)=delete;
    void upload(const double* source) { checked(cudaMemcpy(data,source,count*sizeof(double),cudaMemcpyHostToDevice)); }
    void download(double* target) { checked(cudaMemcpy(target,data,count*sizeof(double),cudaMemcpyDeviceToHost)); }
};
__global__ void evaluate_batch(const double* params,const double* times,const double* positions,
                               const double* weights,const double* wind,int b,int n,
                               double k0,double sigma,bool prior,double* residual,double* jacobian) {
    int i=blockIdx.x*blockDim.x+threadIdx.x;
    if(i>=b) return;
    int m=n*3+(prior?1:0);
    evaluate_fit(params+i*7,times+i*n,positions+i*n*3,weights+i*n*9,wind+i*3,n,k0,sigma,prior,
                 residual+i*m,jacobian+i*m*7);
}
void validate(const Array&,const Array&,const Array&,const Array&,const Array&,double);
class CudaEvaluator {
    int batch,points,rows;
    double k0,sigma;
    bool prior;
    Buffer times,positions,weights,wind,parameters,residual,jacobian;
public:
    CudaEvaluator(Array t,Array p,Array w,Array v,double seed,double noise,bool use_prior):
      batch(t.ndim()==2?static_cast<int>(t.shape(0)):0),points(t.ndim()==2?static_cast<int>(t.shape(1)):0),
      rows(points*3+(use_prior?1:0)),k0(seed),sigma(noise),prior(use_prior),
      times(t.size()),positions(p.size()),weights(w.size()),wind(v.size()),
      parameters(batch*7),residual(batch*rows),jacobian(batch*rows*7) {
        if(batch<1||points<1||p.ndim()!=3||p.shape(0)!=batch||p.shape(1)!=points||p.shape(2)!=3||
           w.ndim()!=4||w.shape(0)!=batch||w.shape(1)!=points||w.shape(2)!=3||w.shape(3)!=3||
           v.ndim()!=2||v.shape(0)!=batch||v.shape(1)!=3||!std::isfinite(k0))
            throw std::invalid_argument("invalid CUDA batch shapes");
        for(int i=0;i<batch;++i) {
            Array zero(7); for(int j=0;j<7;++j) zero.mutable_data()[j]=0;
            Array ti(points,t.data()+i*points),pi({points,3},p.data()+i*points*3),
                  wi({points,3,3},w.data()+i*points*9),vi(3,v.data()+i*3);
            validate(zero,ti,pi,wi,vi,sigma);
        }
        py::gil_scoped_release release;
        times.upload(t.data()); positions.upload(p.data()); weights.upload(w.data()); wind.upload(v.data());
    }
    std::pair<Array,Array> evaluate(Array params) {
        if(params.ndim()!=2||params.shape(0)!=batch||params.shape(1)!=7)
            throw std::invalid_argument("CUDA parameters must have shape (batch,7)");
        for(py::ssize_t i=0;i<params.size();++i) if(!std::isfinite(params.data()[i]))
            throw std::invalid_argument("CUDA parameters must be finite");
        Array r({batch,rows}),j({batch,rows,7});
        {
            py::gil_scoped_release release;
            parameters.upload(params.data());
            evaluate_batch<<<(batch+63)/64,64>>>(parameters.data,times.data,positions.data,weights.data,
                wind.data,batch,points,k0,sigma,prior,residual.data,jacobian.data);
            checked(cudaGetLastError());
            checked(cudaDeviceSynchronize());
            residual.download(r.mutable_data()); jacobian.download(j.mutable_data());
        }
        return {r,j};
    }
};
void bind_cuda(py::module_& module) {
    int count=0;
    module.attr("cuda_available")=(cudaGetDeviceCount(&count)==cudaSuccess&&count>0);
    module.def("cuda_device",[]() {
        int device=0,driver=0; cudaDeviceProp props{};
        checked(cudaGetDevice(&device)); checked(cudaGetDeviceProperties(&props,device));
        checked(cudaDriverGetVersion(&driver));
        return std::string(props.name)+"/"+std::to_string(props.major)+"."+std::to_string(props.minor)+
               "/driver="+std::to_string(driver);
    });
    py::class_<CudaEvaluator>(module,"CudaEvaluator")
        .def(py::init<Array,Array,Array,Array,double,double,bool>())
        .def("evaluate",&CudaEvaluator::evaluate);
}
