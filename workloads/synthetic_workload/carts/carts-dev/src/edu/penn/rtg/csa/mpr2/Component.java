package edu.penn.rtg.csa.mpr2;

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
	private String componentFilename;
	private String componentName;
	private String schedulingPolicy;
	private Vector<Task> taskset;
	private Vector<Task> interfaceTaskset;
	
	
	private MPR2 mPR2Interface;
	private boolean isInterfaceComputed;
	
	private Vector<Component> childComponents;
	private Component parentComponent;
	private boolean isRoot;
	
	
	/**
	 * Function doCSA
	 * This function does the CSA for the system whose top node is the current component
	 * It recursively calls itself and compute all child components. 
	 * When the recursive call reaches the leaf component, it will call computerInterface to compute leaf component's interface
	 * @see computerInterface()
	 * @return 0 correct; 1 wrong
	 */
	public double doCSA(int whichSchedTest, int sbf_type,  String algorithm){
		if(childComponents == null || childComponents.isEmpty()){ //leaf component
			if(whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST 
					|| whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST_FAST
					|| whichSchedTest == GlobalVariable.MENG_SCHEDTEST){
				this.computeInterface_Arvind(true, whichSchedTest,sbf_type, algorithm);
			}else if(whichSchedTest == GlobalVariable.MARKO_SCHEDTEST){
				this.computeInterface_Bertogna(true, sbf_type, algorithm);
			}else{
				System.err.println("Only support Arvind and Marko's test. The input schedulability test name is not supported.");
				System.exit(3);// ERRNO 3 Not supported schedulability test
			}
			
			this.transferInterface2InterfaceTask_InsikApproach();
			isInterfaceComputed = true;
		}else{//non-leaf component
			for(int i=0; i<childComponents.size(); i++){
				childComponents.get(i).doCSA(whichSchedTest,sbf_type, algorithm);
			}
			this.setNonleafComponentWorkload();
			if(whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST 
					|| whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST_FAST 
					|| whichSchedTest == GlobalVariable.MENG_SCHEDTEST){
				this.computeInterface_Arvind(false,whichSchedTest, sbf_type, algorithm);
			}else if(whichSchedTest == GlobalVariable.MARKO_SCHEDTEST){
				this.computeInterface_Bertogna(false, sbf_type, algorithm);
			}else{
				System.err.println("Only support Arvind and Marko's test. The input schedulability test name is not supported.");
				System.exit(3);// ERRNO 3 Not supported schedulability test
			}
				
			this.transferInterface2InterfaceTask_InsikApproach(); //use Theorem 2 in Arvind's 09 paper//use this to check CAMPR is consistent with MPR 
			isInterfaceComputed = true;
		}
		Tool.debug("===Output component " + this.componentName + " information \r\n");
		Tool.debug(this.toString());
		return 0;
	}
	
	/**
	 * Function computeInterface_Arvind
	 * This function compute the MPR interface (Pi, Theta, m') given Pi and the task set
	 * The task set can be the interface task transfered from child components' interface,
	 * which is done by the function which call the computeInterface function.
	 * @return 0 correct; 1 wrong
	 * 
	 */
	private double computeInterface_Arvind(boolean isLeafComponent, int whichSchedTest, int sbf_type, String algorithm){ //finished

//		if(!algorithm.equalsIgnoreCase("gEDF")){
//			System.err.println("ATTENTION:Arvind_SchedTest does not support other algorithms except for gEDF right now.\r\n" +
//					"Please change sched. test name or component's algorithm.");
//			System.exit(3); 
///		}
		
		
		if(this.taskset == null || this.taskset.isEmpty()){
			this.mPR2Interface.setM_prime(0);
			this.mPR2Interface.setTheta(0);
			return 0;
		}
		
		int m_prime_min = this.getMin_m_prime();
		int m_prime_max = this.getMax_m_prime(); //same for gDM and gEDF
		boolean is_interface_feasible = false;
		int m_prime_i = this.getMin_m_prime() - 1;
		Tool.write2log("component "+this.componentName + ", \t m'_min=" + m_prime_min + ", \t m'_max=" + m_prime_max + "\r\n");
		
		MPR2 feasibleInterface = new MPR2();
		MPR2 currentInterface = new MPR2(); //currentInterface may not be feasible; feasibleInterface is to record the final result.
		feasibleInterface.setPi(this.mPR2Interface.getPi());
		currentInterface.setPi(this.mPR2Interface.getPi()); 
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
					is_interface_feasible = true; //This is the min possible interface
					feasibleInterface.setTheta(Pi);
					feasibleInterface.setM_prime(1);
					this.mPR2Interface = feasibleInterface;
					return 0;
				}else{
					is_interface_feasible = false;
					continue;
				}
				
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
					//Ak represents Bk in gDM scheduling with Sanjoy-like sched. test
					double Ak_max = this.getMaxAk(k, m_prime_i, Theta_i, Pi, whichSchedTest, algorithm);//different btween gDM and gEDF
					
					if(Ak_max == GlobalVariable.InterfaceInfeasible){
						is_interface_feasible = false;
						break; 
					}
					Tool.debug("Component name=" + this.componentName  + "\tTheta_i=" + Theta_i + "\t k=" + k + "\t Ak_max=" + Ak_max);
					Tool.write2log("Component name=" + this.componentName  + "\tTheta_i=" + Theta_i + "\t k=" + k + "\t Ak_max=" + Ak_max);
					for(double Ak = 0; Ak <= Ak_max; Ak += GlobalVariable.TIME_PRECISION){
						double Dk = workload.get(k).getDeadline();
						double resource_demand = this.getDBF(Ak, Dk, m_prime_i, k, algorithm);
						double resource_supply = currentInterface.getSBF(Ak+Dk, sbf_type);							
						
						if( resource_demand > resource_supply){
							//Tool.debug("Component " + this.componentName + " currentInterface (" + currentInterface.getPi() + ", " + 
							//		currentInterface.getTheta() + ", " + currentInterface.getM_prime() + ") \t" +  "check task " + k + "\t" + 
							//		"Ak+Dk:" + (Ak+Dk) + 
							//		"getDBF: "+this.getDBF(Ak, Dk, m_prime_i, k) + " > getSBF:" + currentInterface.getSBF(Ak+Dk));
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
		if(feasibleInterface.getTheta() <= 0){
			feasibleInterface.setTheta(GlobalVariable.MAX_INTEGER);
		}
		this.mPR2Interface = feasibleInterface;
		Tool.debug("Component " + this.getComponentName() + " interface: " + this.mPR2Interface.toString() + "\r\n");
		
		return 0;
	}
	
	/**
	 * 8/31/21013
	 * Used to check if an interface is feasible, then the interface with Theta+1 is also feasible.
	 *  i.e., if interface has monotic increase relation.
	 *  This function is only used in experiment to check the monotonic property of Theta, not used in real calculation.
	 * @param whichSchedTest
	 * @param algorithm
	 * @return
	 */
	public double checkThetaMonotonic(int whichSchedTest, int sbf_type, String algorithm){
		algorithm = "gEDF";
		if(whichSchedTest == GlobalVariable.MARKO_SCHEDTEST ){
			System.err.println("whichSchedTest is Bertogna! CheckThetaMonotonic is only for Arvind test!");
			System.exit(1);
		}
		
		
		if(this.taskset == null || this.taskset.isEmpty()){
			for(int i=0; i<this.childComponents.size(); i++){
				this.childComponents.get(i).checkThetaMonotonic(whichSchedTest,sbf_type,  algorithm);
			}
		}
		
		System.out.println("+++++++Start Check Theta Monotonic Property+++++++++++++");
		System.out.println("Monotonic property is if Theta_1 is feasible, then Theta_2 is feasible if Theta_2 > Theta_1, and Pi and m' is the same");
		
		int m_prime_opt = this.mPR2Interface.getM_prime();
		double Theta_opt = this.mPR2Interface.getTheta();
		double Pi_opt = this.mPR2Interface.getPi();
		
		System.out.println("Optimal Interface is (Pi, Theta,m'): (" +Pi_opt + "," + Theta_opt + "," + m_prime_opt + ")");
	
		

		MPR2 currentInterface = new MPR2(); //currentInterface may not be feasible; feasibleInterface is to record the final result.
		currentInterface.setPi(this.mPR2Interface.getPi()); 
		currentInterface.setM_prime(m_prime_opt);


		//brute search feasible theta in [(m'-1)*Pi, m'*Pi]; 
		//Cannot use binary search, because it doesn't necessarily true that when Theta_i is feasible, then Theta_i + 1 is feasible
		//If a feasible Theta exists, m_prime_i is feasible, we get a feasible interface! The m_prime_i will search smaller value
		//If a feasible Theta does not exist, m_prime_i is infeasible; we search m_prime_i in larger value 
		for(double Theta_i = Theta_opt + GlobalVariable.TIME_PRECISION; Theta_i <= m_prime_opt*Pi_opt;
				Theta_i += GlobalVariable.TIME_PRECISION){ //xm: maybe incorrect for Theta_i to start at (m_prime_i-1)*Pi
			currentInterface.setTheta(Theta_i);

			//BE CAREFUL, THE MAX AK WILL BE INFINITE when Theta/Pi - tasksetUtil = 0; Use this condition to avoid infinite Ak
			if(Theta_i/Pi_opt < this.getTasksetUtil()){
				continue;
			}

			//Check if the currentInterface is feasible, i.e.,
			//Check each task k for DEM(A_k+D_k) <= SBF(A_k+D_k)
			Vector<Task> workload = this.taskset;
			for(int k=0; k<workload.size(); k++){
				double Ak_max = this.getMaxAk(k, m_prime_opt, Theta_i, Pi_opt, whichSchedTest, algorithm);

				if(Ak_max == GlobalVariable.InterfaceInfeasible){
					break; 
				}
				//Tool.debug("Check each Ak: Component name=" + this.componentName  + "\tTheta_i=" + Theta_i + "\t k=" + k + "\t Ak_max=" + Ak_max);
				//Tool.write2log("Check each Ak: Component name=" + this.componentName  + "\tTheta_i=" + Theta_i + "\t k=" + k + "\t Ak_max=" + Ak_max);
				for(double Ak = 0; Ak <= Ak_max; Ak += GlobalVariable.TIME_PRECISION){
					double Dk = workload.get(k).getDeadline();

					if(this.getDBF(Ak, Dk, m_prime_opt, k, algorithm) > currentInterface.getSBF(Ak+Dk, sbf_type)){
						//Tool.debug("Component " + this.componentName + " currentInterface (" + currentInterface.getPi() + ", " + 
						//		currentInterface.getTheta() + ", " + currentInterface.getM_prime() + ") \t" +  "check task " + k + "\t" + 
						//		"Ak+Dk:" + (Ak+Dk) + 
						//		"getDBF: "+this.getDBF(Ak, Dk, m_prime_i, k) + " > getSBF:" + currentInterface.getSBF(Ak+Dk));
						String str = "";
						str += "In file" + this.componentFilename + "\r\nHaHa: This task set shows Theta does NOT have monotonic property! ";
						str += "Interface (Pi, Theta, m'): (" 
								+ this.mPR2Interface.getPi() + "," + this.mPR2Interface.getTheta() + "," + this.mPR2Interface.getM_prime() + ") is feasible! \r\n";
						str += "But Interface (Pi, Theta, m'): (" + currentInterface.getPi() + "," + currentInterface.getTheta() + "," + currentInterface.getM_prime() 
								+ ") is NOT feasible!\r\n";
						System.out.println(str);
						Tool.write2log(str);
						
						break;
					}
				}
			} // check all tasks feasibility
			System.out.println("Interface (Pi, Theta,m'): ("+ Pi_opt + "," + Theta_i + "," + m_prime_opt + ") is feasible!");
		} // search Theta_i

		System.out.println("OK. This task set shows Theta has  monotonic property. But other task sets may show Theta has NO monotonic property");
		return 0;
	}
	
	
	/**
	 * Function computeInterface_Bertogna
	 * This is a faster way to compute a component's interface
	 * The schedulability test uses Bertogna' improved schedulability test for gEDF/gDM instead of that in Arvind's paper.
	 * Reason: The schedulability test in Arvind's paper needs to check each Ak in [0, Ak_max], 
	 * the Ak_max can be very large and there may be many tasks, so the checking is very slow
	 * @return 0 correct; 1 wrong
	 * 
	 */
	private double computeInterface_Bertogna(boolean isLeafComponent, int sbf_type, String algorithm){ //finished
//		if(!this.schedulingPolicy.equalsIgnoreCase("gEDF")){
//			Tool.write2log("Component's scheduling policy is not gEDF! It's not supported by the MPR2 resrouce model! exit(1)");
//			System.err.println("Component's scheduling policy is not gEDF! It's not supported by the MPR2 resrouce model! exit(1)");
//			System.exit(1);
//		}
		
		
		if(this.taskset == null || this.taskset.isEmpty()){
			this.mPR2Interface.setM_prime(0);
			this.mPR2Interface.setTheta(0);
			return 0;
		}
		
		int m_prime_min = this.getMin_m_prime();
		int m_prime_max = this.getMax_m_prime_fast();//fast but not 100% correct!
		boolean is_interface_feasible = false;
		int m_prime_i = this.getMin_m_prime() - 1;
		Tool.write2log("component "+this.componentName + ", \t m'_min=" + m_prime_min + ", \t m'_max=" + m_prime_max + "\r\n");
		
		MPR2 feasibleInterface = new MPR2();
		MPR2 currentInterface = new MPR2(); //currentInterface may not be feasible; feasibleInterface is to record the final result.
		feasibleInterface.setPi(this.mPR2Interface.getPi());
		currentInterface.setPi(this.mPR2Interface.getPi()); 
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
/*			if(m_prime_i - this.getTasksetUtil() == 0){
				if(m_prime_i == 1){
					is_interface_feasible = true;
					feasibleInterface.setTheta(Pi);
					feasibleInterface.setM_prime(1);
				}else{
					is_interface_feasible = false;
				}
				continue;
			}*/
			
			//brute search feasible theta in [(m'-1)*Pi, m'*Pi]; 
			//Cannot use binary search, because it doesn't necessarily true that when Theta_i is feasible, then Theta_i + 1 is feasible
			//If a feasible Theta exists, m_prime_i is feasible, we get a feasible interface! The m_prime_i will search smaller value
			//If a feasible Theta does not exist, m_prime_i is infeasible; we search m_prime_i in larger value 
			for(double Theta_i = (m_prime_i-1)*Pi + GlobalVariable.TIME_PRECISION; Theta_i <= m_prime_i*Pi;
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
					double interference = this.getDBF_Bertogna(k, algorithm) ;
					double totalInterference = interference + m_prime_i * (task_k.getExe() - GlobalVariable.ONE_TIME_UNIT);
					double totalSupply = currentInterface.getSBF(task_k.getDeadline(), sbf_type);
					if( totalInterference >= totalSupply ){
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
		this.mPR2Interface = feasibleInterface;
		Tool.debug("Component " + this.getComponentName() + " Computed interface: " + this.mPR2Interface.toString() + "\r\n");
		
		return 0;
	}
	
	public double getDBF_Bertogna(int k, String algorithm){
		double d_k =this.taskset.get(k).getDeadline(); //must be task k in this.taskset
		double dk_ck_1 = this.taskset.get(k).getDeadline() - this.taskset.get(k).getExe() + GlobalVariable.TIME_PRECISION;
		Vector<Task> workload = new Vector<Task>(); //workload with higher priority
		if(algorithm.equalsIgnoreCase("gEDF")){
			workload = this.taskset;
		}else if(algorithm.equalsIgnoreCase("gDM")){
			for(int i=0; i<this.taskset.size(); i++){
				if(this.taskset.get(i).getDeadline() <= d_k) //higher priority
					workload.add(this.taskset.get(i));
			}
		}else{
			System.err.println("Only support algorithm gEDF/gDM. The " + algorithm + " is not supported." );
			System.exit(2);
		}
		
		double result = 0;
		for(int i=0; i<workload.size(); i++){
			double p_i = workload.get(i).getPeriod();
			double e_i = workload.get(i).getExe();
			double d_i = workload.get(i).getDeadline();
			if(i != k)
				//gEDF and gDM have different equation to calculate I_{i,k}; I have paid attention to that here
				if(algorithm.equalsIgnoreCase("gEDF")){ 
					result +=Math.min(dk_ck_1, Math.floor(d_k/p_i) * e_i + Math.min(e_i, d_k - Math.floor(d_k/p_i)*p_i));
				}else if(algorithm.equalsIgnoreCase("gDM")){
					double N_i = Math.floor( (d_k + d_i - e_i) / p_i );
					result += Math.min(dk_ck_1, N_i * e_i + Math.min(e_i, d_k + d_i - e_i - N_i * p_i)); 
				}else {
					System.err.println("Only support algorithm gEDF/gDM. The " + algorithm + " is not supported." );
					System.exit(2);
				}
				
		}
		return result;
	}
	
	/**
	 * Function getmax_m_prime_fast
	 * Get a maximum m' which is not so large to make the MPR calculation faster
	 * Here we assume if a taskset needs 2 times of the taskset.size cores  + 1, it won't be feasible.
	 * So the m' = 10* taskset.size()
	 * @return
	 */
	public int getMax_m_prime_fast(){
		Vector<Task> workload = this.taskset;
		return workload.size()*100 + 1;  
	}
	
	/**
	 * Function setNonleafComponentWorkload
	 * This function set the non-leaf component's workload as the sum of the interface taskset of its child components.
	 */
	private void setNonleafComponentWorkload(){
		for(int i=0; i<this.childComponents.size(); i++){
			Component currentChildComponent = this.childComponents.get(i);
			for(int j=0; j<currentChildComponent.getInterfaceTaskset().size(); j++){
				Vector<Task> currentChildInterfaceTaskset = currentChildComponent.getInterfaceTaskset();
				this.taskset.add(currentChildInterfaceTaskset.get(j));
			}
			
		}
	}
	
	/**
	 * Function transferInterface2InterfaceTask
	 * This function transfer the computed interface of a component to an interface task
	 * The interface task is stored in the interfaceTaskset of this component.
	 * @see computeInterface()
	 * @return 0 correct; 1 wrong;
	 */
	private double transferInterface2InterfaceTask_InsikApproach(){
		
		MPR2 currentInterface = this.mPR2Interface;

		double Pi = currentInterface.getPi();
		double Theta = currentInterface.getTheta();
		double m_prime = currentInterface.getM_prime();
		
		this.interfaceTaskset.clear();
		
		if(Theta < 0 || Theta > m_prime*Pi){ // invalid interface!
			this.interfaceTaskset.add(new Task(Pi,GlobalVariable.MAX_INTEGER,Pi));
			System.out.println("Invalid Interface of Component" + this.componentName + "\r\n");
			return 1;
		}
		if(Theta == 0){
			this.interfaceTaskset.clear();
			return 0;
		}
		

		double alpha = Theta - m_prime*(int)(Math.floor(Theta/m_prime));
		int k=(int) Math.floor(alpha);
		double exec=0;
		Task interfaceTask;
		int num=0;

		//The transformation algorithm is based on Definitioin 2 in Arvind's 09 paper. It can handle when m=1, k=0, corner cases.
		for(int j=0;j<k;j++) {
			exec=(int) (Math.floor(Theta/m_prime)+1);
			interfaceTask =new Task(Pi,exec,Pi);
			interfaceTask.setName("" + interfaceTask.hashCode());
			this.interfaceTaskset.add(interfaceTask);
			Tool.debug("===InterfaceTransfer====" + "interfaceTask " + num + ": " +interfaceTask.toString() + "\r\n");
			num++;
		}
		//Debug.prn(k);
		//interface task k
		if(k == 0){
			exec= Math.floor(Theta/m_prime)+alpha - 0;	//0 is for k*Math.floor(alpha/k). Tested!
		}else{
			exec= Math.floor(Theta/m_prime)+alpha-k*Math.floor(alpha/k);
		}

		interfaceTask =new Task(Pi,exec,Pi);
		interfaceTask.setName("" + interfaceTask.hashCode());
		Tool.debug("===InterfaceTransfer====" + "interfaceTask " + num + ": " + interfaceTask.toString() + "\r\n");
		this.interfaceTaskset.add(interfaceTask);
		num++;

		for(int j=num;j<m_prime;j++) {
			exec=(int) (Math.floor(Theta/m_prime));
			interfaceTask =new Task(Pi,exec,Pi);
			interfaceTask.setName("" + interfaceTask.hashCode());
			this.interfaceTaskset.add(interfaceTask);
			Tool.debug("===InterfaceTransfer===="+ "interfaceTask " + num + ": " + interfaceTask.toString() + "\r\n");
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
	public double getDBF(double Ak, double Dk, int m_prime, int k, String algorithm){ // t_Ak_Dk is A_k+D_k, k is the index of task k.
		if(!algorithm.equalsIgnoreCase("gEDF") && !algorithm.equalsIgnoreCase("gDM")){//task_i's workload in Arvind's test can not be used to compute workload for gDM alg.
			System.err.println("ATTENTION: getDBF: con only support gEDF and gDM algorithm. Not support the algorithm: ." + algorithm);
			//System.exit(2);
		}
		
		Vector<Task> workload = null; //The non-leaf component has no taskset; It only has interface tasks;
		if(algorithm.equalsIgnoreCase("gEDF")){
			 workload = this.taskset;
		}else if(algorithm.equalsIgnoreCase("gDM")){ //"gDM" should not execute! because it is incorrect!
			workload = this.copyHigherPriorityTasks(this.taskset, this.taskset.get(k), "gDM");
		}else{
			System.err.println("getDBF: algorithm is not gEDF or gDM. Exit(1)");
			System.exit(1);
		}
		Task task_k = this.taskset.get(k);
		
		double[] I2_bars = new double[workload.size()];
		double[] I2_hats = new double[workload.size()];
		double[] diff_I2bars_I2hats = new double[workload.size()];
		
		double t_Ak_Dk = Ak + Dk;
		
		//Calculate the Ibar_{i,2} for all i
		for(int i=0; i<workload.size(); i++){
			Task currentTask = workload.get(i);
			if(currentTask.getName() == task_k.getName()){ //ATT: task's name must be unique in whole system.
				I2_bars[i] = Math.min(task_k.getWorkload(t_Ak_Dk, algorithm)-task_k.getExe(), Ak);
			}else{
				I2_bars[i] = Math.min(currentTask.getWorkload(t_Ak_Dk, algorithm), t_Ak_Dk - task_k.getExe());
			}
			
		}
		//Calculate the Ihat_{i,2} for all i
		for(int i=0; i<workload.size(); i++){
			Task currentTask = workload.get(i);
			if(currentTask.getName() == task_k.getName()){//ATT: task's name must be unique in whole system.
				I2_hats[i] = Math.min(task_k.getWorkload(t_Ak_Dk, algorithm) - task_k.getExe() - task_k.getCICO(t_Ak_Dk,algorithm), Ak);
			}else{
				I2_hats[i] = Math.min(currentTask.getWorkload(t_Ak_Dk, algorithm) - currentTask.getCICO(t_Ak_Dk,algorithm), t_Ak_Dk - task_k.getExe());
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
	
	private Vector<Task> copyHigherPriorityTasks(Vector<Task> taskset, Task task_k, String algorithm){
		if(!algorithm.equalsIgnoreCase("gDM")){
			System.err.println("Only support filtering higher priority tasks under gDM");
			System.exit(1);
		}
		Vector<Task> newTaskset = new Vector<Task>();
		for(int i=0; i<taskset.size(); i++){
			if(taskset.get(i).getDeadline() <= task_k.getDeadline()){ //higher priority task
				newTaskset.add(taskset.get(i));
			}
		}
		return newTaskset;
	}
	
	private double getMaxAk(int k, int m_prime, double Theta, double Pi,int whichSchedTest, String algorithm){
		
		final Vector<Task> workload;
		if(algorithm.equalsIgnoreCase("gEDF")){
			workload = this.taskset;
		}else if(algorithm.equalsIgnoreCase("gDM")){
			workload = copyHigherPriorityTasks(this.taskset, this.taskset.get(k),"gDM");
		}else{
			workload = null;
			System.out.println("getMaxAk(): algorithm is not gEDF or gDM. exit(1)");
			System.exit(1);
		}
		
		Task task_k = this.taskset.get(k);
		
		double AkMax = 0;	
		double[] workload_exes = new double[workload.size()]; //ATT:must after workload initilization
		double C_sum = 0;
		double U_tau = 0;
		double U = 0;
		double B = 0;		

		
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
			double numerator = 0;
			if(algorithm.equalsIgnoreCase("gEDF")){
				numerator = workload.get(i).getPeriod() - workload.get(i).getDeadline();
			}else if(algorithm.equalsIgnoreCase("gDM")){
				numerator = workload.get(i).getDeadline() - workload.get(i).getExe();
			}else{
				System.err.println("No such algorithm : " + algorithm );
			}
			U = U + (numerator) * (workload.get(i).getExe() *1.0 / workload.get(i).getPeriod());

		}
		B = B + (Theta / Pi) * (2 + 2*(Pi - Theta/m_prime));
		
		if(whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST || whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST_FAST ){
			AkMax = (C_sum + m_prime*task_k.getExe() - task_k.getDeadline()*(Theta/Pi - U_tau) + U + B) / (Theta/Pi - U_tau);
		}else if(whichSchedTest == GlobalVariable.MENG_SCHEDTEST){
			double B_meng = m_prime * (2 + 2*(Pi - (m_prime -1)));
			AkMax = (C_sum + m_prime*task_k.getExe() - task_k.getDeadline()*(m_prime -1 - U_tau) + U + B_meng) / (m_prime -1 - U_tau);
		}
		

		//Ak's maximum value. Theorem 2 in Arvind's paper.
		//if(whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST_FAST && Theta/Pi - U_tau < GlobalVariable.ONE_TIME_UNIT) return GlobalVariable.MAX_DOUBLE;
		if(Theta/Pi - U_tau < 0){
			return GlobalVariable.InterfaceInfeasible;
		}
		if((whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST || whichSchedTest == GlobalVariable.MENG_SCHEDTEST)
				&& AkMax > GlobalVariable.AK_MAX_BOUND){ //If it's not fast, just abandon the result for this task set!
			Tool.write2Aklog("MPR2\t" + this.componentFilename + "\t Arvind_SchedTest/Meng_SchedTest Ak_max(calculated)" + AkMax + " \t TOO LARGE! system exit. Not compute interface for this task set\r\n");
			Tool.debug("MPR2\t" + this.componentFilename + "\t Arvind_SchedTest/Meng_SchedTest Ak_max(calculated)" + AkMax + " \t TOO LARGE! system exit. Not compute interface for this task set\r\n");
			System.err.println("MPR2\t" + this.componentFilename + "\t Arvind_SchedTest/Meng_SchedTest Ak_max(calculated)" + AkMax + " \t TOO LARGE! Computation is very slow.\r\n");
			
			//System.exit(1);
		}

		if(whichSchedTest == GlobalVariable.ARVIND_SCHEDTEST_FAST  //if it's Fast calculation, then it just skip this Theta and try the next theta
				&& AkMax >= GlobalVariable.AK_MAX_BOUND){
			Tool.write2Aklog("MPR2\t" + this.componentFilename + "\t Ak_max(calculated)" + AkMax + "\r\n");
			return GlobalVariable.InterfaceInfeasible;
		}
		
		
		return Math.max(0, AkMax);
		
		
		
	}
	
	
	/*
	 * ATTENTION: THE m'_max IS INCORRECT! BECAUSE YOU NEED TO GUARANTEE DEM < SBF, NOT DEM < t*m'_max
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
		if(true) // control if we use the workload.size() as the m'_max; true if we use workload.size()
			return workload.size()* GlobalVariable.MAX_NUMCORES_TO_CHECK_MULTIPLIER; 

		Tool.debug("ComponentName: " + this.componentName + "taskset.size:" + this.taskset.size() + "interfaceTask.size" + this.interfaceTaskset.size() +"\r\n");
		double diff_di_ci_min = workload.get(0).getDeadline() - workload.get(0).getExe();	//e_i is C_i in Arvind's paper
		if( diff_di_ci_min - 0 == GlobalVariable.MIN_DOUBLE){ // Lemma 3 in Arvind's paper has mistake, when denominator is 0, the m'_max is infinite.
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
		this.mPR2Interface = new MPR2();
		this.isInterfaceComputed = false;
		this.childComponents = new Vector<Component>();
		this.taskset = new Vector<Task>();
		this.interfaceTaskset = new Vector<Task>();
		
		this.componentName = componentName;
		this.schedulingPolicy = schedulingPolicy;
		//System.out.println("period="+interfacePeriod+"!");
		this.mPR2Interface.setPi(Double.parseDouble(interfacePeriod));
		this.parentComponent = parentComponent;
		this.isRoot = isRoot;
	
	}
	
	public Component(){
		super();
		this.mPR2Interface = new MPR2();
		this.isInterfaceComputed = false;
		this.childComponents = new Vector<Component>();
		this.taskset = new Vector<Task>();
		this.interfaceTaskset = new Vector<Task>();
		
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
		str += "(" + this.mPR2Interface.getPi() + "," + this.mPR2Interface.getTheta() + "," + this.mPR2Interface.getM_prime() + ") \r\n";		
		str += "------InterfaceTaskset-----\r\n";
		for(int i=0; i<this.interfaceTaskset.size(); i++){
			str += this.interfaceTaskset.get(i).toString();
		}
		str += "=============================\r\n";
		
		return str;
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
	
	
	public String getComponentFilename() {
		return componentFilename;
	}

	public void setComponentFilename(String componentFilename) {
		this.componentFilename = componentFilename;
	}

	public MPR2 getmPR2Interface() {
		return mPR2Interface;
	}

	public void setmPR2Interface(MPR2 mPR2Interface) {
		this.mPR2Interface = mPR2Interface;
	}

//	/**
//	 * Test: Meng's sbf and dbf is consistent with Jaewoo's
//	 * @param args
//	 */
//	public static void main(String args[]){
//		double t = 40;
//		MPR2 testMPR = new MPR2(10, 27.2,3);
//		Component testComponent = new Component();
//		Vector<Task> taskset = new Vector<Task>();
//		taskset.add(new Task(20,1,20));
//		taskset.add(new Task(40,3,40));
//		taskset.add(new Task(40,2,40));
//		taskset.add(new Task(40,20,40));
//		taskset.add(new Task(40,20,40));
//		taskset.add(new Task(50,20,50));
//		testComponent.setTaskset(taskset);
//		Tool.debug("SBF: " + testMPR.getSBF(t) + "\t DBF" + testComponent.getDBF(0.0, 40, 3, 3)+"\r\n");
//		
//	}
	

}
