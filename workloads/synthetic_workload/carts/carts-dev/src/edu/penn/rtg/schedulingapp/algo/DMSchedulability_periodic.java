package edu.penn.rtg.schedulingapp.algo;

import java.util.Vector;

import edu.penn.rtg.common.GlobalVariable;
import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.util.SchException;
import edu.penn.rtg.schedulingapp.util.UserUtil;
/**
 * Compute optimal bandwidth and deadline (DM, Periodic).
 * this class has two main function<P>
 * 1. Compute optimal bandwidth <BR>
 * Using schedulability test, it compute optimal bandwidth <P>
 * 2. transform a resource model  into a single task<P>
 * supported resource model : Periodic Resource Model  <BR>
 * supported scheduling algorithm : DM
 * <P>
 * @author      
 * @version     1.0
 * @since       1.0
 */
public class DMSchedulability_periodic {

	private int resPeriod;
	private SchedulingComponent C;
	/**
	 * Constructor
	 * It set target component and target period
	 * @param  period given period
	 * @param  C	target component
	 */
	public DMSchedulability_periodic(SchedulingComponent C, int resPeriod)
			throws Exception {
		if (!C.isDM()) {
			UserUtil.show("The component has algorithm set to EDF. Cannot continue");
			throw new SchException();
		}
		this.C = C;
		this.resPeriod = resPeriod;
	}
	// Not using yet ... it contains problem 
	public double getNewBandwidth()
	{
		Vector<?> taskV=C.getTasks(resPeriod);
		double max_bandwidth=0;
		for(int i=0;i<taskV.size();i++)
		{
			Task task=(Task)taskV.get(i);
			double period=task.getPeriod();
			double demand=C.computeRBF(period, i, resPeriod);
			double bandwidth=demand/period;
			if(max_bandwidth<bandwidth) max_bandwidth=bandwidth;
			//System.out.println(i+","+demand+","+period);
			//System.out.println(i+","+bandwidth+","+max_bandwidth);
		}
		return max_bandwidth;

	}
	
	/**
	 * //GlobalVariable.IMPL_METHOD == GlobalVariable.MENG_IMPL
	 * Meng's implementation of PRM on DM
	 * @return min bandwidth of an interface under a given period
	 * @author Meng Xu
	 */
	public double getBandwidth_mengImpl(){
		double Pi = resPeriod;
		double minBandwidth = 100;
		
		for(double currTheta = 0; true; currTheta += GlobalVariable.TIME_PRECISION){
			boolean isCurrThetaSched = true;
			Vector<Task> taskset =  this.C.getTasks(resPeriod); //DeadlineAscending sorted tasks
			for(int index=0; index < this.C.getSize(resPeriod); index++){
				boolean task_index_sched = false;
				for(double t=GlobalVariable.TIME_PRECISION; t<=taskset.get(index).getDeadline(); t+=GlobalVariable.TIME_PRECISION){
					//calculate rbf_index 
					double rbf_index_t = 0, sbf_t = 0;
					for(int j=0; j<=index; j++){
						rbf_index_t += Math.ceil(t/taskset.get(j).getPeriod()) * taskset.get(j).getExecution(); 
					}
					//calculate sbf_t
					if(t < Pi - currTheta){
						sbf_t = 0;
					}else{
						sbf_t = Math.floor( (t - (Pi - currTheta) ) / Pi ) * currTheta
								+ Math.max(0, t - 2*(Pi - currTheta) - Math.floor( (t - (Pi-currTheta) )/Pi )*Pi);
					}
					
					if(rbf_index_t <= sbf_t){
						task_index_sched = true;
						break;
					}
				}
				if(task_index_sched == false){
					//currTheta is not schedulable
					isCurrThetaSched = false;
					break;
				}
			}
			
			//avoid infinite loop in rare cases
			if(currTheta > Pi * 100){
				minBandwidth = Pi * 100;
				return minBandwidth;
			}
			
			if(isCurrThetaSched == false){
				continue;
			}else{
				return currTheta * 1.0 / resPeriod;
			}
			
		}
		
	}
	
	/**
	 * It calculates optimal bandwidth of given component and given period
	 * by using schedulability test. 
	 *
	 * @return      optimal bandwidth.
	 * @author Jaewoo Lee
	 * @see         none
	 */

	@SuppressWarnings("unused")
	public double getBandwidth() {
		
		if(GlobalVariable.IMPL_METHOD != GlobalVariable.JAEWOO_IMPL){
			return getBandwidth_mengImpl();
		}
		
		double minBandwidth = 0;
		double time = 0, tprime = 0, tprime0 = 0, tprime1 = 0;
		double olddemand = 0;
		int k = 0;
		double alpha = 0, delta = 0;
		double s0 = 0, s1 = -1, f0 = 0, f1 = 0;

		double theta = 0, theta1, theta2, thetaOpt = 0;
		double bandwidth = 0;
		//System.out.println("Comp:" + C.getCompName());
		for (int index = 0; index < this.C.getSize(resPeriod); index++) {

			double period = this.C.getTasks(resPeriod).get(index).getPeriod();
			double exec = this.C.getTasks(resPeriod).get(index).getExecution();

			
			if (exec <= 0 || period <= 0)
				continue;
			time = period;
			double taskBandwidth = 100;
			@SuppressWarnings("unused")
			double taskIntersection = 0;
			olddemand = 0;
			while (time > 0) {

				double demand = C.computeRBF(time, index, resPeriod);
				if (demand == olddemand) {
					time = time - 1;
					continue;
				}
				olddemand = demand;

				k = (int) Math.floor(time / this.resPeriod);
				alpha = time - k * this.resPeriod;

				delta = this.resPeriod;
				theta = 0;
				f0 = Math.floor((alpha - delta + theta) / this.resPeriod);
				tprime0 = f0 * this.resPeriod + k * this.resPeriod;
				// tprime should not be negative ( 2010.1.27 : Jaewoo Lee)
				tprime0 = Math.max(0, tprime0);
				s0 = (theta / this.resPeriod) * (tprime0 - (delta - theta));

				if (f0 == -1) {
					theta = delta - alpha;
					f1 = Math.floor((alpha - delta + theta) / this.resPeriod);
					tprime1 = f1 * this.resPeriod + k * this.resPeriod;
					// tprime should not be negative ( 2010.1.27 : Jaewoo Lee)
					tprime1 = Math.max(0, tprime1);
					s1 = (theta / this.resPeriod) * (tprime1 - (delta - theta));

				}

				if ((s1 > s0) && (s1 <= demand))
					tprime = tprime1;
				else
					tprime = tprime0;

				theta1 = demand * this.resPeriod / tprime;
				theta2 = (demand + tprime + 2 * this.resPeriod - time)
						* this.resPeriod / (tprime + 2 * this.resPeriod);
				thetaOpt = Math.min(Math.max(theta1, 0), Math.max(theta2, 0));
				bandwidth = thetaOpt / this.resPeriod;
				// System.out.println(bandwidth);
				if (taskBandwidth > bandwidth) {

					taskIntersection = time;
					taskBandwidth = bandwidth;
				}
				time = time - 1;
			}
			// /*
			if (minBandwidth < taskBandwidth) {

				minBandwidth = taskBandwidth;
			}
			

		}
		// if(this.resPeriod == 10)
		// System.out.println((new Double(this.resPeriod)).toString() + " " +
		// (new Double(minBandwidth)).toString());
		//System.out.println("min:" + minBandwidth);
		return minBandwidth;
	}

	/**
	 * Depending on the scheduling algorithm employed by object c, it transform 
	 * given resource model into a task with given period(periodic resource model). 
	 * @param  edp target resource model
	 * @param  period given period
	 * @return      A Task characterizing a periodic task with given period.
	 * @see         Task
	 */
	Task T_DM(ResourceModel edp, int period) {
		return (new Task(edp.getPeriod(), edp.getBandwidth() * edp.getPeriod(),
				edp.getPeriod()));
	}

}
