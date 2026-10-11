#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "kernel.hpp"
namespace py=pybind11;
using Array=py::array_t<double,py::array::c_style|py::array::forcecast>;

void validate(const Array& parameters,const Array& times,const Array& positions,
              const Array& weights,const Array& wind,double sigma) {
    int n=static_cast<int>(times.size());
    if(parameters.ndim()!=1 || parameters.size()!=7 || times.ndim()!=1 || n<1 ||
       positions.ndim()!=2 || positions.shape(0)!=n || positions.shape(1)!=3 ||
       weights.ndim()!=3 || weights.shape(0)!=n || weights.shape(1)!=3 || weights.shape(2)!=3 ||
       wind.ndim()!=1 || wind.size()!=3 || !std::isfinite(sigma) || sigma<=0.0)
        throw std::invalid_argument("invalid native trajectory array shapes or prior noise");
    for(const Array* a : {&parameters,&times,&positions,&weights,&wind})
        for(py::ssize_t j=0;j<a->size();++j) if(!std::isfinite(a->data()[j]))
            throw std::invalid_argument("native trajectory inputs must be finite");
    for(int j=0;j<n;++j) if(times.data()[j]<0 || times.data()[j]>3600 || (j && times.data()[j]<times.data()[j-1]))
        throw std::invalid_argument("native timestamps must be nondecreasing, nonnegative and at most one hour");
}

std::pair<Array,Array> evaluate(Array parameters,Array times,Array positions,Array weights,Array wind,
                              double k0,double sigma,bool prior) {
    validate(parameters,times,positions,weights,wind,sigma);
    if(!std::isfinite(k0)) throw std::invalid_argument("prior seed must be finite");
    int n=static_cast<int>(times.size()), m=3*n+(prior?1:0);
    Array residual(m), jacobian({m,7});
    {
        py::gil_scoped_release release;
        evaluate_fit(parameters.data(),times.data(),positions.data(),weights.data(),wind.data(),
                     n,k0,sigma,prior,residual.mutable_data(),jacobian.mutable_data());
    }
    return {residual,jacobian};
}

#ifdef PITCHTRACKER_CUDA
void bind_cuda(py::module_& module);
#endif
PYBIND11_MODULE(_pitchtracker_native,module) {
    module.attr("version")="0.1.0";
    module.def("evaluate",&evaluate);
#ifdef PITCHTRACKER_CUDA
    bind_cuda(module);
#else
    module.attr("cuda_available")=false;
#endif
}
