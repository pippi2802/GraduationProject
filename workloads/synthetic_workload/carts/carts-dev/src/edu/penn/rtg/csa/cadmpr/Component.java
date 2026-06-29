package edu.penn.rtg.csa.cadmpr;

import java.util.*;

import edu.penn.rtg.common.*;





/**
 * Class Component.
 * It's a POJO, storing component information(taskset,scheduler,interface,child components)
 * 
 * JDK version used: <JDK1.7>
 * @author Meng Xu
 * Create Date: 4/4/2013 
 *
 */
public class Component {
	private String componentName;
	private String schedulingPolicy;
	private Vector<Task> taskset;
	private Vector<Task> interfaceTaskset;
	private Vector<Task> interfaceTaskset_taskcentricUB_only;
	
	private CADMPR dMPRInterface;
	private CADMPR dMPRInterface_taskcentricUB_only;
	private boolean isInterfaceComputed;
	
	private Vector<Component> childComponents;
	private Component parentComponent;
	private boolean isRoot;
	private String componentFilename;
	
	
	/**
	 * Function doCSA
	 * This function does the CSA for the system whose top node is the current component
	 * It recursively calls itself and compute all child components. 
	 * When the recursive call reaches the leaf component, it will call computerInterface to compute leaf component's interface
	 * @see computerInterface()
	 * @return 0 correct; 1 wrong
	 */
	public double doCSA(int whichSchedTest, int whichApproach){
		
		if(childComponents == null || childComponents.isEmpty()){
			if(whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST || whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST_FAST) 
				this.computeInterface_Arvind(true, whichSchedTest, whichApproach);
			else 
				this.computeInterface_Bertogna(true, whichApproach);
			
			this.transferInterface2InterfaceTask_ArvindApproach(); //must be before TASK_CENTRIC_UB, otherwise, interface task will be added twice!
			
			/*If it's TASKCENTRIC_UB cache aware analysis, we need to use the interface with smaller bandwidth*/
			//Be careful: Need to get the interface upper bound for this.dMPRInterface_taskcentricUB_only before call this!
			if(whichApproach == GlobalVariable.TASK_CENTRIC_UB){
				double bw_taskcentric = this.dMPRInterface.getTheta() * 1.0 / this.dMPRInterface.getPi() + this.dMPRInterface.getM_dedicatedCores();
				double bw_taskcentric_ub_only = this.dMPRInterface_taskcentricUB_only.getTheta() * 1.0 / this.dMPRInterface_taskcentricUB_only.getPi() + this.dMPRInterface_taskcentricUB_only.getM_dedicatedCores();
				if(bw_taskcentric > bw_taskcentric_ub_only){ /*choose the one with smaller interface*/
						this.dMPRInterface = this.dMPRInterface_taskcentricUB_only;
						this.interfaceTaskset = this.interfaceTaskset_taskcentricUB_only;
				}
			}
			
			isInterfaceComputed = true;
		}else{
			for(int i=0; i<childComponents.size(); i++){
				childComponents.get(i).doCSA(whichSchedTest, whichApproach);
			}
			//init the taskset for each non-leaf component for each computation! Because the child component's interface changes.
			this.taskset.clear();
			this.setNonleafComponentWorkload();
			if(whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST || whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST_FAST) 
				this.computeInterface_Arvind(false, whichSchedTest,whichApproach);
			else 
				this.computeInterface_Bertogna(false,whichApproach);
			
			this.transferInterface2InterfaceTask_ArvindApproach(); 
			isInterfaceComputed = true;
		}
		Tool.debug("===Output component " + this.componentName + " information \r\n");
		Tool.debug(this.toString());
		return 0;
	}
	
	public void resetDelta_crpmd(){
		if((this.childComponents == null || this.childComponents.isEmpty()) 
				&& (this.taskset != null && !this.taskset.isEmpty())){ //leaf component with tasks 
			
			for(int i=0; i<this.taskset.size(); i++){
				Task currentTask = this.taskset.get(i);
				currentTask.setDelta_crpmd(1.9);			
			}
		}else{
			for(int i=0; i<this.childComponents.size(); i++){
				this.childComponents.get(i).resetDelta_crpmd();
			}
		}
		System.out.println("reset the crpmd as 1.9ms which is only for the experiment");
		
	}
	
	public double getMaxOhInSystem(){
		if((this.childComponents == null || this.childComponents.isEmpty()) 
				&& (this.taskset != null && !this.taskset.isEmpty())){
			double maxOh = 0;
			for(int i=0; i<this.taskset.size(); i++){
				Task currentTask = this.taskset.get(i);
				if(maxOh < currentTask.getDelta_crpmd()){
					maxOh = currentTask.getDelta_crpmd();
				}
			}
			return maxOh;
		}else{
			double maxOh = 0;
			for(int i=0; i<this.childComponents.size(); i++){
				double currentOh = this.childComponents.get(i).getMaxOhInSystem();
				if(maxOh < currentOh){
					maxOh = currentOh;
				}
			}
			return maxOh;
		}
	}
	
	/**
	 * Function inflateTaskWCET_taskCentric(Component component)
	 * Inflate each task's WCET with *all* cache overhead. 
	 * This function is recursively called from the root component and
	 * inflate all tasks' WCET with cache overheads in the whole CSA tree
	 * @see readMe in this package.
	 */
	public void inflateTaskWCET_taskCentric(boolean useMaxOh, double maxOh){
	
		if((this.childComponents == null || this.childComponents.isEmpty()) 
				&& (this.taskset != null && !this.taskset.isEmpty())){ //leaf component with tasks 
			double delta_crpmd_ecb = 0; //the max crpmd \tau_i can cause in the domain
			for(int i=0; i<this.taskset.size(); i++){
				Task currentTask = this.taskset.get(i);
				if(delta_crpmd_ecb < currentTask.getDelta_crpmd())
					delta_crpmd_ecb = currentTask.getDelta_crpmd();
			}
			for(int i=0; i<this.taskset.size(); i++){
				Task currentTask = this.taskset.get(i);
				double inflated_exe;
				if(useMaxOh == false){
					inflated_exe = currentTask.getExe() 
							+ delta_crpmd_ecb
							+ currentTask.getDelta_crpmd() * this.getNumberofVCPUPreemptionEvent(currentTask.getPeriod(), GlobalVariable.TASK)
							+ currentTask.getDelta_crpmd() *  this.getNumberofVCPUFinishEvent(currentTask.getPeriod(), GlobalVariable.TASK);
				}else{
					inflated_exe = currentTask.getExe() 
							+ maxOh
							+ maxOh * this.getNumberofVCPUPreemptionEvent(currentTask.getPeriod(), GlobalVariable.TASK)
							+ maxOh *  this.getNumberofVCPUFinishEvent(currentTask.getPeriod(), GlobalVariable.TASK);
				}
				
				currentTask.setExe(inflated_exe);
			}
		}else{
			for(int i=0; i<this.childComponents.size(); i++){
				this.childComponents.get(i).inflateTaskWCET_taskCentric(useMaxOh, maxOh);
			}
		}

			
	}
	/**
	 * Function inflateTaskWCET_onlyVCPUEvent(Component component)
	 * Inflate each task's WCET with *VCPU-stop event* cache overhead. 
	 * This function is recursively called from the root component and
	 * inflate all tasks' WCET with cache overheads in the whole CSA tree
	 * @see readMe in this package.
	 */
	public void inflateTaskWCET_onlyVCPUEvent(boolean useMaxOh, double maxOh){
		if((this.childComponents == null || this.childComponents.isEmpty()) 
				&& (this.taskset != null && !this.taskset.isEmpty())){ //leaf component with tasks 
			for(int i=0; i<this.taskset.size(); i++){
				Task currentTask = this.taskset.get(i);
				/*Here is the difference between inflateTaskWCET_taskCentric() */
				double inflated_exe;
				if(useMaxOh == false){
					inflated_exe = currentTask.getExe() 
							+ currentTask.getDelta_crpmd() * this.getNumberofVCPUPreemptionEvent(currentTask.getPeriod(), GlobalVariable.TASK)
							+ currentTask.getDelta_crpmd() *  this.getNumberofVCPUFinishEvent(currentTask.getPeriod(), GlobalVariable.TASK);
				}else{
					inflated_exe = currentTask.getExe() 
							+ maxOh * this.getNumberofVCPUPreemptionEvent(currentTask.getPeriod(), GlobalVariable.TASK)
							+ maxOh *  this.getNumberofVCPUFinishEvent(currentTask.getPeriod(), GlobalVariable.TASK);
				}
				currentTask.setExe(inflated_exe);	
			}
		}else{
			for(int i=0; i<this.childComponents.size(); i++){
				this.childComponents.get(i).inflateTaskWCET_onlyVCPUEvent(useMaxOh, maxOh);
			}
		}		
	}
	
	/**
	 * Fnction inflateTaskWCET_Bjorn
	 * Only account for the cache overhead cause by Event 1(higher priority task release event)
	 * Inflate each task's WCET with *one* cache overhead caused by higher priority task release event.
	 * This approach uses Bjorn's accounting technique, i.e., inflate higher priority task with one max CRPMD it can causes.
	 */
	public void inflateTaskWCETEV1_Bjorn(boolean useMaxOh, double maxOh){
		if((this.childComponents == null || this.childComponents.isEmpty()) 
				&& (this.taskset != null && !this.taskset.isEmpty())){ //leaf component with tasks 
			double delta_crpmd_ecb = 0; //the max crpmd \tau_i can cause in the domain
			for(int i=0; i<this.taskset.size(); i++){
				Task currentTask = this.taskset.get(i);
				if(delta_crpmd_ecb < currentTask.getDelta_crpmd())
					delta_crpmd_ecb = currentTask.getDelta_crpmd();
			}
			for(int i=0; i<this.taskset.size(); i++){
				Task currentTask = this.taskset.get(i);
				double inflated_exe;
				if(useMaxOh == false){
					inflated_exe = currentTask.getExe() + delta_crpmd_ecb;
				}else{
					inflated_exe = currentTask.getExe() + maxOh;
				}
				
				currentTask.setExe(inflated_exe);			
			}
		}else{
			for(int i=0; i<this.childComponents.size(); i++){
				this.childComponents.get(i).inflateTaskWCETEV1_Bjorn(useMaxOh, maxOh);
			}
		}
		
		
	}
	
	/**
	 * Function getNumberofHigherPriorityTaskReleaseEvent
	 * 
	 * In the analysis, t is the task_k's period
	 * @param k is the task k which is preempted by the higher priority task
	 * @param t is the time interval during which the task k is preempted 
	 * @return the number of higher priority task release event, i.e., the max number of preemption event, of task k during time interval t.
	 */
	public int getNumberofHigherPriorityTaskReleaseEvent(int k, double t){
		Vector<Task> workload = this.taskset;
		Task task_k = workload.get(k);
		int eventNumber = 0;
		for(int i=0; i<workload.size(); i++){
			Task currentTask = workload.get(i);
			if(i != k && currentTask.getPeriod() < task_k.getPeriod()){ //preempting task j
				eventNumber += (int)Math.floor((t - currentTask.getExe())/currentTask.getPeriod()) + 1;
			}
		}
		return eventNumber;
	}
	
	/**
	 * Function getNumberofVCPUPreemptionEvent( double t)
	 * It will return the number of VCPUPreemptionEvent for this domain during the time interval t. 
	 * t is a task's period because we want to calculate the number of such events during a task's lifetime.
	 * @param t the time interval during which the event happens. It's usually the period of task i.
	 * @param duringWhosePeriod decides which equation to use to calculate the #of preemption event. 
	 * The equation is different for the same t duing a task tau_k's period and a VP_i's period
	 * @return
	 */
	public int getNumberofVCPUPreemptionEvent(double t, int duringWhosePeriod){
		Component parentComponent = this.parentComponent;
		if(parentComponent == null || parentComponent.childComponents.isEmpty()){
		//	Tool.write2log("getNumberofVCPUPreemptionEvent(t): its parent component is NULL! NO VCPU Preemption Event! Direct return 0! ");
		//	System.out.println("ATTENTION:getNumberofVCPUPreemptionEvent(t): its parent component is NULL! NO VCPU Preemption Event! Direct return 0!");
			return 0;
		}
		int eventNumber = 0;
		Vector<Component> childComponents = parentComponent.getChildComponents();
		
		for(int i=0; i<childComponents.size(); i++){
			Component currentComponent = childComponents.get(i);
			if(currentComponent.getCacheAwareMPRInterface().getPi() 
					< this.getCacheAwareMPRInterface().getPi()){
				switch(duringWhosePeriod){
				case GlobalVariable.TASK: eventNumber += (int)Math.ceil(t/currentComponent.getCacheAwareMPRInterface().getPi()); break;
				case GlobalVariable.VCPU: eventNumber += (int)Math.ceil((t-currentComponent.getCacheAwareMPRInterface().getPi())/currentComponent.getCacheAwareMPRInterface().getPi()); break;
				default: System.err.println("Error in getNumberofVCPUPreeptionEvent(): Must be TASK or VCPU!");				
				}
					
			}
		}
		return eventNumber;
		
	}
	
	/**
	 * Function getNumberofVCPUFinishEvent( double t)
	 * It returns the number of VCPU Budget Finish event of this component during time interval t
	 * @param duringWhosePeriod decides using which equation to calculate the number. 
	 * 			It's different to calculate the preemption number for a task or a VP_i.
	 * @param t
	 * @return
	 */
	public int getNumberofVCPUFinishEvent(double t, int duringWhosePeriod){
		
		double currentPi = this.dMPRInterface.getPi();
		double currentBi = this.dMPRInterface.getTheta();
		int resultNum = 0;
		if(duringWhosePeriod == GlobalVariable.TASK){
			resultNum = (int)Math.ceil( (t - currentBi) / currentPi ) + 1;
		}
		if(duringWhosePeriod == GlobalVariable.VCPU){
			resultNum = 1;
		}
		return resultNum;
	}
	
	
	/**
	 * Function computeInterface_Arvind
	 * This function compute the MPR interface (Pi, Theta, m') given Pi and the task set
	 * The task set can be the interface task transfered from child components' interface,
	 * which is done by the function which call the computeInterface function.
	 * @return 0 correct; 1 wrong
	 * 
	 */
	private double computeInterface_Arvind(boolean isLeafComponent, int whichSchedTest, int whichApproach){ //finished
//		if( (this.componentName.equalsIgnoreCase("system") && !this.schedulingPolicy.equalsIgnoreCase("hybridEDF")) ||
//				(!this.componentName.equalsIgnoreCase("system") && !this.schedulingPolicy.equalsIgnoreCase("gEDF"))){
//			System.err.println("Component does not uses the hybridEDF or gEDF. The Cache Aware MPR only support gEDF for leaf component, hybrid EDF for hypervisor. exit(1)");
//			Tool.write2log("Component does not uses the hybridEDF or gEDF. The Cache Aware MPR only support gEDF for leaf component, hybrid EDF for hypervisor. exit(1)");
//			System.exit(1);
//		}
		
		
		if(this.taskset == null || this.taskset.isEmpty()){
			this.dMPRInterface.setM_prime(0);
			this.dMPRInterface.setTheta(0);
			return 0;
		}
		
		int m_prime_min = this.getMin_m_prime();
		int m_prime_max = this.getMax_m_prime();
		boolean is_interface_feasible = false;
		int m_prime_i = this.getMin_m_prime() - 1;
		Tool.write2log("component "+this.componentName + ", \t m'_min=" + m_prime_min + ", \t m'_max=" + m_prime_max + "\r\n");
		
		CADMPR feasibleInterface = new CADMPR();
		CADMPR currentInterface = new CADMPR(); //currentInterface may not be feasible; feasibleInterface is to record the final result.
		feasibleInterface.setPi(this.dMPRInterface.getPi());
		feasibleInterface.setM_dedicatedCores(this.dMPRInterface.getM_dedicatedCores());
		currentInterface.setPi(this.dMPRInterface.getPi()); 
		currentInterface.setM_dedicatedCores(this.dMPRInterface.getM_dedicatedCores());
		double Pi = feasibleInterface.getPi();	//Assume period is given by designer and it only has one value
		
		do{ // binary search m' in [m'_min, m'_max]
			if(is_interface_feasible == false){
				m_prime_min = m_prime_i + 1;
			}else{
				m_prime_max = m_prime_i - 1;
			}
			if(m_prime_min > m_prime_max){
				break;
			}
			m_prime_i = (m_prime_min + m_prime_max) / 2;
			currentInterface.setM_prime(m_prime_i);
			
			//m'- taskset.util == 0, special case to test m'_i's feasibility
			if(m_prime_i - this.getTasksetUtil() == 0){
				if(m_prime_i == 1){
					is_interface_feasible = true;
					feasibleInterface.setTheta(Pi);
					feasibleInterface.setM_prime(1);
				}else{
					is_interface_feasible = false;
				}
				continue;
			}
			
			//brute search feasible theta in [(m'-1)*Pi, m'*Pi]; 
			//Cannot use binary search, because it doesn't necessarily true that when Theta_i is feasible, then Theta_i + 1 is feasible
			//If a feasible Theta exists, m_prime_i is feasible, we get a feasible interface! The m_prime_i will search smaller value
			//If a feasible Theta does not exist, m_prime_i is infeasible; we search m_prime_i in larger value 
			for(double Theta_i = (m_prime_i-1)*Pi+GlobalVariable.TIME_PRECISION; Theta_i <= m_prime_i*Pi;
					Theta_i += GlobalVariable.TIME_PRECISION){ //xm: maybe incorrect for Theta_i to start at (m_prime_i-1)*Pi
				currentInterface.setTheta(Theta_i);
				
				//BE CAREFUL, THE MAX AK WILL BE INFINITE when Theta/Pi - tasksetUtil = 0; Use this condition to avoid infinite Ak
				if(Theta_i/Pi < this.getTasksetUtil()){
					is_interface_feasible = false;
					continue;
				}
			
				//Check if the currentInterface is feasible, i.e.,
				//Check each task k for DEM(A_k+D_k) <= SBF(A_k+D_k)
				is_interface_feasible = true;
				Vector<Task> workload = this.taskset;
				for(int k=0; k<workload.size(); k++){
					double Ak_max = this.getMaxAk(k, m_prime_i, Theta_i, Pi, whichApproach, whichSchedTest);
					if(whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST_FAST && Ak_max >= GlobalVariable.AK_MAX_BOUND){
						is_interface_feasible = false;
						Tool.write2Aklog("CADMPR\t" + "Arvind_Sched_Fast" + "\t"  + this.componentFilename + "\t Ak_max(calculated)" + Ak_max + "\r\n");
						Tool.debug("CADMPR\t" + "Arvind_Sched_Fast" + "\t"  + this.componentFilename + "\t Ak_max(calculated)" + Ak_max + "\r\n");
						break; //must break to avoid the following unnecessary checking.
					}
					if(Ak_max == GlobalVariable.InterfaceInfeasible){
						is_interface_feasible = false;
						break; 
					}
					Tool.debug("Component name=" + this.componentName  + "\tTheta_i=" + Theta_i + "\t k=" + k + "\t Ak_max=" + Ak_max);
					Tool.write2log("Component name=" + this.componentName  + "\tTheta_i=" + Theta_i + "\t k=" + k + "\t Ak_max=" + Ak_max);
					for(double Ak = 0; Ak <= Ak_max; Ak += GlobalVariable.TIME_PRECISION){
						double Dk = workload.get(k).getDeadline();
						double demand = this.getDBF(Ak, Dk, m_prime_i, k);
						double supply = currentInterface.getSBF_CADMPR(Ak+Dk, whichApproach, this);
						if( demand > supply){
//							Tool.debug("Component " + this.componentName + " currentInterface (" + currentInterface.getPi() + ", " + 
//									currentInterface.getTheta() + ", " + currentInterface.getM_prime() + ") \t" +  "check task " + k + "\t" + 
//									"Ak+Dk:" + (Ak+Dk) + 
//									"getDBF: "+this.getDBF(Ak, Dk, m_prime_i, k) + " > getSBF:" + currentInterface.getSBF(Ak+Dk));
							is_interface_feasible = false;
							break;
						}
					}
					if(is_interface_feasible == false) 	break;					
				} // check all tasks feasibility
				
				if(is_interface_feasible == true){
					feasibleInterface.setM_prime(currentInterface.getM_prime());
					feasibleInterface.setTheta(currentInterface.getTheta());
					
					break; // get the min feasible Theta, and set it as the component's interface
				}
				
			} // search Theta_i
			
		}while(true); //search m_prime_i
		//The last feasibleInterface is the min bandwidth interface! 
		
		if(feasibleInterface.getTheta() <= 0 ){// no feasible interface!
			feasibleInterface.setTheta(GlobalVariable.MAX_INTEGER);
		}
		
		this.dMPRInterface = feasibleInterface;
		Tool.debug("Component " + this.getComponentName() + " interface: " + this.dMPRInterface.toString() + "\r\n");
		
		return 0;
	}
	
	/**
	 * Function computeInterface_Bertogna
	 * This is a faster way to compute a component's interface
	 * The schedulability test uses Bertogna' improved schedulability test for gEDF instead of that in Arvind's paper.
	 * Reason: The schedulability test in Arvind's paper needs to check each Ak in [0, Ak_max], 
	 * the Ak_max can be very large and there may be many tasks, so the checking is very slow
	 * @return 0 correct; 1 wrong
	 * 
	 */
	private double computeInterface_Bertogna(boolean isLeafComponent, int whichApproach){ //finished
//		if(!this.schedulingPolicy.equalsIgnoreCase("gEDF")){
//			Tool.write2log("Component's scheduling policy is not gEDF! It's not supported by the MPR2 resrouce model! exit(1)");
//			System.err.println("Component's scheduling policy is not gEDF! It's not supported by the MPR2 resrouce model! exit(1)");
//			System.exit(1);
//		}
		
		
		if(this.taskset == null || this.taskset.isEmpty()){
			this.dMPRInterface.setM_prime(0);
			this.dMPRInterface.setTheta(0);
			return 0;
		}
		
		int m_prime_min = this.getMin_m_prime();
		int m_prime_max = this.getMax_m_prime_fast();//fast but not 100% correct!
		boolean is_interface_feasible = false;
		int m_prime_i = this.getMin_m_prime() - 1;
		Tool.write2log("component "+this.componentName + ", \t m'_min=" + m_prime_min + ", \t m'_max=" + m_prime_max + "\r\n");
		
		CADMPR feasibleInterface = new CADMPR();
		CADMPR currentInterface = new CADMPR(); //currentInterface may not be feasible; feasibleInterface is to record the final result.
		feasibleInterface.setPi(this.dMPRInterface.getPi());
		feasibleInterface.setM_dedicatedCores(this.dMPRInterface.getM_dedicatedCores());
		currentInterface.setPi(this.dMPRInterface.getPi()); 
		currentInterface.setM_dedicatedCores(this.dMPRInterface.getM_dedicatedCores());
		double Pi = feasibleInterface.getPi();	//Assume period is given by designer and it only has one value
		
		do{ // binary search m' in [m'_min, m'_max]
			if(is_interface_feasible == false){
				m_prime_min = m_prime_i + 1;
			}else{
				m_prime_max = m_prime_i - 1;
			}
			if(m_prime_min > m_prime_max){
				break;
			}
			m_prime_i = (m_prime_min + m_prime_max) / 2;
			currentInterface.setM_prime(m_prime_i);
			
			//m'- taskset.util == 0, special case to test m'_i's feasibility
			if(m_prime_i - this.getTasksetUtil() == 0){
				if(m_prime_i == 1){
					is_interface_feasible = true;
					feasibleInterface.setTheta(Pi);
					feasibleInterface.setM_prime(1);
				}else{
					is_interface_feasible = false;
				}
				continue;
			}
			
			//brute search feasible theta in [(m'-1)*Pi, m'*Pi]; 
			//Cannot use binary search, because it doesn't necessarily true that when Theta_i is feasible, then Theta_i + 1 is feasible
			//If a feasible Theta exists, m_prime_i is feasible, we get a feasible interface! The m_prime_i will search smaller value
			//If a feasible Theta does not exist, m_prime_i is infeasible; we search m_prime_i in larger value 
			for(double Theta_i = (m_prime_i-1)*Pi; Theta_i <= m_prime_i*Pi;
					Theta_i += GlobalVariable.TIME_PRECISION){ //xm: maybe incorrect for Theta_i to start at (m_prime_i-1)*Pi
				currentInterface.setTheta(Theta_i);
				
				//BE CAREFUL, THE MAX AK WILL BE INFINITE when Theta/Pi - tasksetUtil = 0; Use this condition to avoid infinite Ak
				if(Theta_i/Pi < this.getTasksetUtil()){
					is_interface_feasible = false;
					continue;
				}
			
				//Check if the currentInterface is feasible, i.e.,
				//Check each task k for DEM(A_k+D_k) <= SBF(A_k+D_k)
				is_interface_feasible = true;
				Vector<Task> workload = this.taskset;
				for(int k=0; k<workload.size(); k++){
					Task task_k = workload.get(k);
					if(this.getDBF_Bertogna(k) 
							> currentInterface.getSBF_CADMPR(task_k.getDeadline() - task_k.getExe() + GlobalVariable.ONE_TIME_UNIT, whichApproach, this)){
						is_interface_feasible = false;
						break;
					}					
					
				} // check all tasks feasibility
				
				if(is_interface_feasible == true){
					feasibleInterface.setM_prime(currentInterface.getM_prime());
					feasibleInterface.setTheta(currentInterface.getTheta());
					
					break; // get the min feasible Theta, and set it as the component's interface
				}
				
			} // search Theta_i
			
		}while(true); //search m_prime_i
		//The last feasibleInterface is the min bandwidth interface! 
		if(feasibleInterface.getTheta() < 0){
			feasibleInterface.setTheta(GlobalVariable.MAX_INTEGER);
		}
		this.dMPRInterface = feasibleInterface;
		Tool.debug("Component " + this.getComponentName() + " Computed interface: " + this.dMPRInterface.toString() + "\r\n");
		
		return 0;
	}
	
	public double getDBF_Bertogna(int k){
		Vector<Task> workload = this.taskset;
		double result = 0;
		double d_k = workload.get(k).getDeadline();
		double dk_ck_1 = workload.get(k).getDeadline() - workload.get(k).getExe() + GlobalVariable.TIME_PRECISION;
		for(int i=0; i<workload.size(); i++){
			if(i != k)
				result += Math.min(workload.get(i).getWorkload(d_k),dk_ck_1);
		}
		return result;
	}
	
	/**
	 * Function getmax_m_prime_fast
	 * Get a maximum m' which is not so large to make the MPR calculation faster
	 * Here we assume if a taskset needs 10 times of the taskset.size cores, it won't be feasible.
	 * So the m' = 10* taskset.size()
	 * @return
	 */
	public int getMax_m_prime_fast(){
		Vector<Task> workload = this.taskset;
		return workload.size()*10+1;  
	}
	
	
	/**
	 * Function setNonleafComponentWorkload
	 * This function set the non-leaf component's workload as the sum of the non full utilization interface taskset of its child components.
	 * The full utilization interface tasks are counted into parent component's interface's m_dedicatedCores. 
	 */
	private void setNonleafComponentWorkload(){
		for(int i=0; i<this.childComponents.size(); i++){
			Component currentChildComponent = this.childComponents.get(i);
			for(int j=0; j<currentChildComponent.getInterfaceTaskset().size(); j++){
				Vector<Task> currentChildInterfaceTaskset = currentChildComponent.getInterfaceTaskset();
				if(currentChildInterfaceTaskset.get(j).getExe() == currentChildInterfaceTaskset.get(j).getPeriod()){
					int m_dedicatedCores = this.dMPRInterface.getM_dedicatedCores();
					m_dedicatedCores++;
					this.dMPRInterface.setM_dedicatedCores(m_dedicatedCores);
				}else{
					this.taskset.add(currentChildInterfaceTaskset.get(j));
				}
			}
			
		}
	}
	
	/**
	 * Function transferInterface2InterfaceTask_ArvindApproach
	 * This function transfer the computed interface of a component to an interface task
	 * The interface tasks are stored in the interfaceTaskset of this component.
	 * @see computeInterface()
	 * @return 0 correct; 1 wrong;
	 */
	private double transferInterface2InterfaceTask_ArvindApproach(){
		
		CADMPR currentInterface = this.dMPRInterface;

		double Pi = currentInterface.getPi();
		double Theta = currentInterface.getTheta();
		int m_prime = currentInterface.getM_prime();
		int m_dedicatedCores = currentInterface.getM_dedicatedCores();
		
		if(Theta < (m_prime-1)*Pi || Theta > m_prime*Pi){ // invalid interface!
			this.interfaceTaskset.add(new Task(Pi,GlobalVariable.MAX_INTEGER,Pi));
			Tool.debug("Invalid Interface of Component" + this.componentName + "\r\n");
			return 1;
		}
		
		//transfer the dedicatedCores to full utilization task. These tasks will be abstracted to dedicated cores in the parent component
		for(int i=0; i<m_dedicatedCores; i++){
			this.interfaceTaskset.add(new Task(Pi,Pi,Pi));
		}

		if(m_prime > 0 && Theta > (m_prime-1)*Pi){
			for(int j=0; j<m_prime-1; j++){
				this.interfaceTaskset.add(new Task(Pi,Pi,Pi));
			}
			this.interfaceTaskset.add(new Task(Pi, Theta-(m_prime-1)*Pi, Pi));
		}
		
		
		//Debug: if it's correct to transfer interface to interface task
		Tool.debug("-----The transfered interface task as Component (" + this.componentName + ")'s workload----- \r\n");
		for(int i=0; i<this.interfaceTaskset.size(); i++){
			Tool.debug(this.interfaceTaskset.get(i).toString() + "\r\n");
		}
		
		return 0;
	}
	
	/**
	 * Function getDBF
	 * It return DEM(A_k+D_k)
	 * return the dbf value for task \tau_k when parallel is m_prime
	 * LHS of Theorem 1 of Arvind's paper "Optimal virtual cluster-based multiprocessor scheduling".
	 */
	public double getDBF(double Ak, double Dk, int m_prime, int k){ // t_Ak_Dk is A_k+D_k, k is the index of task k.
		Vector<Task> workload = this.taskset; //The non-leaf component has no taskset; It only has interface tasks;
		double[] I2_bars = new double[workload.size()];
		double[] I2_hats = new double[workload.size()];
		double[] diff_I2bars_I2hats = new double[workload.size()];
		Task task_k = workload.get(k);
		double t_Ak_Dk = Ak + Dk;
		
		//Calculate the Ibar_{i,2} for all i
		for(int i=0; i<workload.size(); i++){
			Task currentTask = workload.get(i);
			if(i == k){
				I2_bars[i] = Math.min(task_k.getWorkload(t_Ak_Dk)-task_k.getExe(), Ak);
			
			}else{
				I2_bars[i] = Math.min(currentTask.getWorkload(t_Ak_Dk), t_Ak_Dk - task_k.getExe());
			}
			
		}
		//Calculate the Ihat_{i,2} for all i
		for(int i=0; i<workload.size(); i++){
			Task currentTask = workload.get(i);
			if(i == k){
				I2_hats[i] = Math.min(task_k.getWorkload(t_Ak_Dk) - task_k.getExe() - task_k.getCI(t_Ak_Dk), Ak);
			}else{
				I2_hats[i] = Math.min(currentTask.getWorkload(t_Ak_Dk) - currentTask.getCI(t_Ak_Dk), t_Ak_Dk - task_k.getExe());
			}
		}
		//Calculate L_{m'-1}, the max (m'-1) (Ibar_2 - Ihat_2)
		for(int i=0; i<workload.size(); i++){
			diff_I2bars_I2hats[i] = Math.max(0, I2_bars[i] - I2_hats[i]); //The m'-1 carry tasks' workload, which cannot be negative
		}
		Arrays.sort(diff_I2bars_I2hats); //sort in ascending order
		//Debug the sort result
		//System.out.println("Sorted array in ascending order.");
		//for(int i=0; i<workload.size(); i++){
		//	System.out.print("" + diff_I2bars_I2hats[i] + ",");
		//}
		//System.out.flush();
		//System.out.println("\n");
		
		//DEM(A_k+D_k,m') equation
		double result = 0;
		result = m_prime*task_k.getExe();
		for(int i=0; i<workload.size(); i++){
			result = result + I2_hats[i];
		}
		for(int i=1; i <= Math.min(m_prime-1, workload.size()); i++){
			result = result + diff_I2bars_I2hats[workload.size()-i];
		}
		
		return result;	
		
	}
	
	/**
	 * 
	 * @param k
	 * @param m_prime
	 * @param Theta
	 * @param Pi
	 * @param whichApproach TaskCentric approach or ModelCentric approach
	 * @return The max Ak to check
	 */
	private double getMaxAk(int k, int m_prime, double Theta, double Pi, int whichApproach, int whichSchedTest){
		double AkMax = 0;
		if(whichApproach == GlobalVariable.TASK_CENTRIC || whichApproach == GlobalVariable.TASK_CENTRIC_UB){//The maximu Ak in TASKCENTRIC approach
			Vector<Task> workload = this.taskset;
			double[] workload_exes = new double[workload.size()];
			double C_sum = 0;
			double U_tau = 0;
			double U = 0;
			double Theta_part = 0;
			double B_prime = 0;
		
			
			//initialize the intermediate variable
			for(int i=0; i<workload.size();i++){
				workload_exes[i] = workload.get(i).getExe();
			}
			Arrays.sort(workload_exes); 	//in ascending order
			for(int i=1; i<=m_prime-1;i++){
				if(workload.size()-i < 0) break;
				//Tool.debug("Component name:" + this.componentName + ", m':" + m_prime + ", i:" + i + ", workload.size:"+ workload.size() + "\r\n");
				C_sum = C_sum + workload_exes[workload.size()-i];
				
			}
			for(int i=0; i<workload.size();i++){
				U_tau = U_tau + workload.get(i).getExe()/workload.get(i).getPeriod(); 
				U = U + (workload.get(i).getPeriod() - workload.get(i).getDeadline()) * (workload.get(i).getExe() / workload.get(i).getPeriod());
			}
			Theta_part = Theta - (m_prime - 1)* Pi;
			B_prime = 2*Theta_part*(Pi - Theta_part)/Pi;
			
			//Ak's maximum value. Theorem 2 in Arvind's paper.
			double numerator =(C_sum + m_prime*workload.get(k).getExe() - workload.get(k).getDeadline()*(Theta/Pi - U_tau) + U + B_prime);
			double denominator = (Theta/Pi - U_tau);
			AkMax = numerator/denominator;
			
			if(denominator < 0 || denominator < GlobalVariable.MIN_DOUBLE){//effective bandwidth < taskset util then LHS > RHS
				return GlobalVariable.InterfaceInfeasible;
			}
			if(whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST 
					&& AkMax > GlobalVariable.AK_MAX_BOUND){
				Tool.write2Aklog("MPR2\t" + this.componentFilename + "\t Arvind_SchedTest Ak_max(calculated)" + AkMax + " \t TOO LARGE! return infeasible interface\r\n");
				Tool.debug("MPR2\t" + this.componentFilename + "\t Arvind_SchedTest Ak_max(calculated)" + AkMax + " \t TOO LARGE! return infeasible interface\r\n");
				return GlobalVariable.InterfaceInfeasible;
				
			}
			
		}
		
		if(whichApproach == GlobalVariable.MODEL_CENTRIC){
			Vector<Task> workload = this.taskset;
			double[] workload_exes = new double[workload.size()];
			double C_sum = 0, U_tau = 0, U = 0, Theta_part = 0, Theta_star = 0, Theta_prime = 0;
			double x1 = 0, x2 =0, z = 0, delta_crpmd_max = 0;
			int N_ev23_pi = 0;
			
			//initialize the intermediate variable
			for(int i=0; i<workload.size();i++){
				workload_exes[i] = workload.get(i).getExe();
			}
			Arrays.sort(workload_exes); 	//in ascending order
			for(int i=1; i<=m_prime-1;i++){
				if(workload.size()-i < 0) break;
				//Tool.debug("Component name:" + this.componentName + ", m':" + m_prime + ", i:" + i + ", workload.size:"+ workload.size() + "\r\n");
				 C_sum = C_sum + workload_exes[workload.size()-i];
				
			}
			for(int i=0; i<workload.size();i++){
				 U_tau = U_tau + workload.get(i).getExe()/workload.get(i).getPeriod(); 
				 U = U + (workload.get(i).getPeriod() - workload.get(i).getDeadline()) * (workload.get(i).getExe() / workload.get(i).getPeriod());
			}
			Theta_part = Theta - (m_prime - 1)* Pi;
			//calculate the number of stop event during a period of VP_i, i..e, N_ev23_pi
			N_ev23_pi = this.getNumberofVCPUPreemptionEvent(Pi, GlobalVariable.VCPU) + this.getNumberofVCPUFinishEvent(Pi, GlobalVariable.VCPU);
			delta_crpmd_max = this.getMaxCRPMDinComponent();
			Theta_star = Math.max(0, Theta_part - N_ev23_pi*delta_crpmd_max);
			x1 = Pi - delta_crpmd_max - Theta_star;
			z = Pi - Theta_star;
			x2 = N_ev23_pi*delta_crpmd_max;
			Theta_prime = Math.max(0, Pi - x2);
			double numerator = C_sum + m_prime*workload.get(k).getExe() + U + (x1 + z)*(Theta_star/Pi) + 2*x2*(m_prime-1)*(Theta_prime/Pi);
			double denominator = (Theta_star/Pi) + Theta_prime*(m_prime-1)/Pi - U_tau ;
			AkMax = numerator/denominator - workload.get(k).getDeadline();
			
			if(denominator < 0 || denominator < GlobalVariable.MIN_DOUBLE){//effective bandwidth < taskset util then LHS > RHS
				return GlobalVariable.InterfaceInfeasible;
			}
			if(whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST 
					&& AkMax > GlobalVariable.AK_MAX_BOUND){
				Tool.write2Aklog("MPR2\t" + this.componentFilename + "\t Arvind_SchedTest Ak_max(calculated)" + AkMax + " \t Computation is very slow. Consider change to ARVIND_SCHEDTEST_FAST!\r\n");
				//System.exit(1);
				
			}
			
			
		}
		
		return Math.max(0, AkMax);
		
	}
	
	/**
	 * GetMaxCRPMDinComponent
	 * When the domain is non-leaf domain, the value is 0 because the interface task has overhead 0
	 * @return The maximum crpmd in this domain/component
	 */
	public double getMaxCRPMDinComponent(){
		double delta_crpmd_max = 0; //the max crpmd \tau_i can cause in the domain
		for(int i=0; i<this.taskset.size(); i++){
			Task currentTask = this.taskset.get(i);
			if(delta_crpmd_max < currentTask.getDelta_crpmd())
				delta_crpmd_max = currentTask.getDelta_crpmd();
		}
		return delta_crpmd_max;
	}
	
	
	
	/*
	 * Function getMax_m_prime
	 * Return the maximum m' value, with which the MPR model can guarantees schedulability of C.
	 * Lemma 3 in Arvind's paper. It's not tight! because it implicitly assume each task's util <= 1. So at most n processors can guarantee schedule those tasks.
	 * DEM(Ak+Dk) <= n(Ak+Dk), while (Pi, n*Pi, n) has sbf = n(Ak+Dk)
	 * This is the improvement upper bound of m' than the Lemma 3 in Arvind's paper. 
	 */
	private int getMax_m_prime(){
		double m_prime_max = 0;
		double C_total = 0;
		Vector<Task> workload = this.taskset;
		if(true)
			return workload.size() * GlobalVariable.MAX_NUMCORES_TO_CHECK_MULTIPLIER; 

		Tool.debug("ComponentName: " + this.componentName + "taskset.size:" + this.taskset.size() + "interfaceTask.size" + this.interfaceTaskset.size() +"\r\n");
		double diff_di_ci_min = workload.get(0).getDeadline() - workload.get(0).getExe();	//e_i is C_i in Arvind's paper
		if( diff_di_ci_min - 0 == 0){ // Lemma 3 in Arvind's paper has mistake, when denominator is 0, the m'_max is infinite.
			return workload.size()*10 + 1; // because each task's util <=1, so so many task set is enough!
		}
		
		for(int i=0; i<workload.size(); i++){
			C_total = C_total + workload.get(i).getExe();
			if(workload.get(i).getDeadline() - workload.get(i).getExe() < diff_di_ci_min)
				diff_di_ci_min = workload.get(i).getDeadline() - workload.get(i).getExe();
		}
		
		m_prime_max = C_total / diff_di_ci_min + workload.size();
		return (int)Math.ceil(m_prime_max);
	}
	
	/*
	 * Function getMin_m_prime
	 * Return the min m' value. It's ceil(sum_{\tau}(e_i/p_i))
	 */
	private int getMin_m_prime(){
		double util_total = 0;
		Vector<Task> workload = this.taskset;

		for(int i=0; i<workload.size(); i++){
			util_total = util_total + workload.get(i).getExe()/workload.get(i).getPeriod();
		}
		return (int)Math.ceil(util_total);
	}
	
	/**
	 * Function getTasksetUtil
	 * Return the component's taskset's total utilization
	 * @return
	 */
	private double getTasksetUtil(){
		double tasksetUtil = 0;
		Vector<Task> workload = this.taskset;

		for(int i=0; i<workload.size(); i++){
			tasksetUtil += workload.get(i).getExe() / workload.get(i).getPeriod();
		}
		return tasksetUtil;
	}
	
	
	
	/////////////////////////////////
	public void addChildComponent(Component childComponent){
		this.childComponents.add(childComponent);
	}
	
	public void addTask(Task task){
		this.taskset.add(task);
	}
	
	//////////////////Construct function///////////////////////////////
	public Component(String componentName, String schedulingPolicy, String interfacePeriod, Component parentComponent, boolean isRoot){
		this.dMPRInterface = new CADMPR();
		this.dMPRInterface_taskcentricUB_only = new CADMPR();
		this.isInterfaceComputed = false;
		this.childComponents = new Vector<Component>();
		this.taskset = new Vector<Task>();
		this.interfaceTaskset = new Vector<Task>();
		
		this.componentName = componentName;
		this.schedulingPolicy = schedulingPolicy;
		//System.out.println("period="+interfacePeriod+"!");
		this.dMPRInterface.setPi(Double.parseDouble(interfacePeriod));
		this.dMPRInterface_taskcentricUB_only.setPi(Double.parseDouble(interfacePeriod));
		this.parentComponent = parentComponent;
		this.isRoot = isRoot;
	
	}
	
	public Component(){
		super();
		this.dMPRInterface = new CADMPR();
		this.dMPRInterface_taskcentricUB_only = new CADMPR();
		this.isInterfaceComputed = false;
		this.childComponents = new Vector<Component>();
		this.taskset = new Vector<Task>();
		this.interfaceTaskset = new Vector<Task>();
	}
	
	/**
	 * Deep copy a Component
	 * @param fromComponent
	 */
	public Component(Component component, Component parentComponent){
		this.componentName = component.getComponentName();
		this.componentFilename = component.getComponentFilename();
		this.schedulingPolicy = component.getSchedulingPolicy();
		this.isInterfaceComputed = component.isInterfaceComputed();
		this.isRoot = component.isRoot();
		this.parentComponent = parentComponent;
		this.dMPRInterface = new CADMPR(component.getCacheAwareMPRInterface());
		this.taskset = new Vector<Task>();
		for(Task task: component.getTaskset()){
			Task newTask = new Task(task);
			this.taskset.add(newTask);
		}
		this.interfaceTaskset = new Vector<Task>();
		for(Task task: component.getInterfaceTaskset()){
			Task newTask = new Task(task);
			this.interfaceTaskset.add(newTask);
		}
		this.childComponents = new Vector<Component>();
		for(Component child: component.getChildComponents()){
			Component newChild = new Component(child, this);
			this.childComponents.add(newChild);
		}
	}
	
	/**
	 * Function toString
	 * Return the component's property, including the name of the parent component and child components.	
	 */
	public String toString(){
		String str = "==================================\r\n";
		str += "componentName:"+ this.componentName + " schedulingPolicy:" + this.schedulingPolicy +
				" isRoot: " + this.isRoot + " isInterfaceComputed:" + this.isInterfaceComputed + "\r\n";
		if(this.parentComponent != null)
			str += "parentComponentName: " + this.parentComponent.getComponentName() + "\r\n";
		str += "----Child Components' Name----------------\r\n";
		for(int i=0; i<this.childComponents.size();i++){
			str += "Child " + i + " Name: " + this.childComponents.get(i).getComponentName() + "\r\n";
		}
		str += "------Taskset-------------\r\n";
		for(int i=0;i<this.taskset.size();i++){
			str += this.taskset.get(i).toString();
		}
		str += "------Interface-------------\r\n";
		str += "(" + this.dMPRInterface.getPi() + "," + this.dMPRInterface.getTheta() + "," + this.dMPRInterface.getM_prime() + ") \r\n";		
		str += "------InterfaceTaskset-----\r\n";
		for(int i=0; i<this.interfaceTaskset.size(); i++){
			str += this.interfaceTaskset.get(i).toString();
		}
		str += "=============================\r\n";
		
		return str;
	}
	
	public void set_taskcentricUBOnly_interface_and_interfacetasks_for_all_leaf( ){ 
		if(childComponents == null || childComponents.isEmpty()){
			this.set_taskcentricUBOnly_interface_and_interfacetasks( );
		}else{
			for(int i=0; i<childComponents.size(); i++){
				this.getChildComponents().get(i).set_taskcentricUBOnly_interface_and_interfacetasks_for_all_leaf();
			}
		}
	}
	
	public void set_taskcentricUBOnly_interface_and_interfacetasks(){
		this.dMPRInterface_taskcentricUB_only.setM_dedicatedCores(this.dMPRInterface.getM_dedicatedCores());
		this.dMPRInterface_taskcentricUB_only.setM_prime(this.dMPRInterface.getM_prime());
		this.dMPRInterface_taskcentricUB_only.setPi(this.dMPRInterface.getPi());
		double theta_ub = Math.ceil( this.dMPRInterface.getTheta() * 1.0 / this.dMPRInterface.getPi() ) * this.dMPRInterface.getPi();
		this.dMPRInterface_taskcentricUB_only.setTheta(theta_ub);
		
		this.interfaceTaskset_taskcentricUB_only = new Vector<Task>();
		for(int i = 0; i < this.interfaceTaskset.size(); i++){
			Task task_ub = this.interfaceTaskset.get(i);
			if(task_ub.getExe() * 1.0 / task_ub.getPeriod() < 1){
				task_ub.setExe(task_ub.getPeriod());
			}
			Task task = this.interfaceTaskset.get(i).clone();
			this.interfaceTaskset_taskcentricUB_only.add(task);
		}
		
	}
	
	public void clear_cadmpr_interface_and_interfacetasks_for_all_nodes(){
		if(childComponents == null || childComponents.isEmpty()){
			this.clear_cadmpr_interface_and_interfacetasks();
		}else{
			for(int i=0; i<childComponents.size(); i++){
				this.getChildComponents().get(i).clear_cadmpr_interface_and_interfacetasks_for_all_nodes();
			}
			this.clear_cadmpr_interface_and_interfacetasks();
		}
	}
	
	public void clear_cadmpr_interface_and_interfacetasks(){
		this.dMPRInterface.clear();
		this.interfaceTaskset.clear();
	}

	
	//////////Below are get set function for properties//////////////////////////
	public Vector<Task> getTaskset() {
		return taskset;
	}
	public void setTaskset(Vector<Task> taskset) {
		this.taskset = taskset;
	}
	public String getSchedulingPolicy() {
		return schedulingPolicy;
	}
	public void setSchedulingPolicy(String schedulingPolicy) {
		this.schedulingPolicy = schedulingPolicy;
	}
	public CADMPR getCacheAwareMPRInterface() {
		return dMPRInterface;
	}
	public void setCacheAwareMPRInterface(CADMPR dMPRInterface) {
		this.dMPRInterface = dMPRInterface;
	}
	public Vector<Component> getChildComponents() {
		return childComponents;
	}
	public void setChildComponents(Vector<Component> childComponents) {
		this.childComponents = childComponents;
	}

	public boolean isInterfaceComputed() {
		return isInterfaceComputed;
	}

	public void setInterfaceComputed(boolean isInterfaceComputed) {
		this.isInterfaceComputed = isInterfaceComputed;
	}

	public Component getParentComponent() {
		return parentComponent;
	}

	public void setParentComponent(Component parentComponent) {
		this.parentComponent = parentComponent;
	}

	public boolean isRoot() {
		return isRoot;
	}

	public void setRoot(boolean isRoot) {
		this.isRoot = isRoot;
	}

	public String getComponentName() {
		return componentName;
	}

	public void setComponentName(String componentName) {
		this.componentName = componentName;
	}

	public Vector<Task> getInterfaceTaskset() {
		return interfaceTaskset;
	}

	public void setInterfaceTaskset(Vector<Task> interfaceTaskset) {
		this.interfaceTaskset = interfaceTaskset;
	}
	
	public CADMPR getdMPRInterface() {
		return dMPRInterface;
	}

	public void setdMPRInterface(CADMPR dMPRInterface) {
		this.dMPRInterface = dMPRInterface;
	}

	public String getComponentFilename() {
		return componentFilename;
	}

	public void setComponentFilename(String componentFilename) {
		this.componentFilename = componentFilename;
	}

/*	*//**
	 * Test: Meng's sbf and dbf is consistent with Jaewoo's
	 * @param args
	 *//*
	public static void main(String args[]){
		double t = 40;
		CADMPR testMPR = new CADMPR(10, 27.2,3);
		Component testComponent = new Component();
		Vector<Task> taskset = new Vector<Task>();
		taskset.add(new Task(20,1,20));
		taskset.add(new Task(40,3,40));
		taskset.add(new Task(40,2,40));
		taskset.add(new Task(40,20,40));
		taskset.add(new Task(40,20,40));
		taskset.add(new Task(50,20,50));
		testComponent.setTaskset(taskset);
		Tool.debug("SBF: " + testMPR.getSBF_CADMPR(t, GlobalVariable.MODEL_CENTRIC, testComponent) + "\t DBF" + testComponent.getDBF(0.0, 40, 3, 3)+"\r\n");
		
	}*/
	
	

}
